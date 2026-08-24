#include <EEPROM.h>

// OverheadLink Mega firmware v0.3.0
// Safe rule: pins start high-impedance. Ordinary outputs are enabled only by a
// validated CONFIG + APPROVE_OUT sequence. Peripheral pins are explicitly
// reserved before a driver may use them.

static const char* FW_VERSION = "0.3.0";
static const uint8_t FIRST_PIN = 2;
static const uint8_t LAST_PIN = 69;  // A15 on Mega 2560
static const uint8_t PIN_COUNT = 70;
static const unsigned long SERIAL_BAUD = 115200UL;
static const uint16_t ANALOG_REPORT_MS = 50;
static const uint16_t HEARTBEAT_MS = 1000;
static const uint8_t TM_DELAY_US = 5;

enum PinRole : uint8_t {
  ROLE_NONE = 0,
  ROLE_INPUT = 1,
  ROLE_ANALOG = 2,
  ROLE_OUTPUT = 3,
  ROLE_PERIPHERAL = 4
};

struct PinState {
  PinRole role;
  bool activeLow;
  bool approvedOutput;
  bool raw;
  bool stable;
  uint16_t debounceMs;
  unsigned long lastRawChange;
  unsigned long pulseUntil;
  int analogValue;
  unsigned long lastAnalogReport;
};

struct IdentityRecord {
  uint32_t magic;
  char uuid[17];
  char name[33];
};

struct Tm1637State {
  bool configured;
  uint8_t clkPin;
  uint8_t dioPin;
  uint8_t brightness;
};

static const uint32_t IDENTITY_MAGIC = 0x4F4C4944UL;  // OLID
PinState pins[PIN_COUNT];
IdentityRecord identity;
Tm1637State tm1637 = {false, 0, 0, 7};
bool running = false;
bool learnInputs = false;
bool learnAnalog = false;
unsigned long lastHeartbeat = 0;
char lineBuffer[220];
uint16_t lineLength = 0;

uint8_t checksumBody(const char* body) {
  uint8_t value = 0;
  while (*body) value ^= static_cast<uint8_t>(*body++);
  return value;
}

void sendBody(const char* body) {
  uint8_t crc = checksumBody(body);
  Serial.print(body);
  Serial.print('|');
  if (crc < 16) Serial.print('0');
  Serial.println(crc, HEX);
}

void sendError(const char* code) {
  char body[96];
  snprintf(body, sizeof(body), "OL1|ERR|%s", code);
  sendBody(body);
}

void sendIdent() {
  char body[120];
  snprintf(body, sizeof(body), "OL1|IDENT|MEGA|%s|%s|%s", identity.uuid, identity.name, FW_VERSION);
  sendBody(body);
}

void sendDigital(uint8_t pin, bool value) {
  char body[64];
  snprintf(body, sizeof(body), "OL1|DIN|%u|%u|%lu", pin, value ? 1 : 0, millis());
  sendBody(body);
}

void sendAnalog(uint8_t pin, int value) {
  char body[64];
  snprintf(body, sizeof(body), "OL1|AIN|%u|%d|%lu", pin, value, millis());
  sendBody(body);
}

void setPhysicalOutput(uint8_t pin, bool on) {
  if (pin > LAST_PIN || pins[pin].role != ROLE_OUTPUT) return;
  bool level = pins[pin].activeLow ? !on : on;
  digitalWrite(pin, level ? HIGH : LOW);
}

// ---------------- TM1637 ----------------

void tmDrive(uint8_t pin, bool high) {
  pinMode(pin, OUTPUT);
  digitalWrite(pin, high ? HIGH : LOW);
}

void tmStart() {
  tmDrive(tm1637.clkPin, true);
  tmDrive(tm1637.dioPin, true);
  delayMicroseconds(TM_DELAY_US);
  tmDrive(tm1637.dioPin, false);
  delayMicroseconds(TM_DELAY_US);
  tmDrive(tm1637.clkPin, false);
}

void tmStop() {
  tmDrive(tm1637.clkPin, false);
  tmDrive(tm1637.dioPin, false);
  delayMicroseconds(TM_DELAY_US);
  tmDrive(tm1637.clkPin, true);
  delayMicroseconds(TM_DELAY_US);
  tmDrive(tm1637.dioPin, true);
  delayMicroseconds(TM_DELAY_US);
}

bool tmWriteByte(uint8_t value) {
  for (uint8_t bit = 0; bit < 8; ++bit) {
    tmDrive(tm1637.clkPin, false);
    tmDrive(tm1637.dioPin, (value & 0x01) != 0);
    delayMicroseconds(TM_DELAY_US);
    tmDrive(tm1637.clkPin, true);
    delayMicroseconds(TM_DELAY_US);
    value >>= 1;
  }
  tmDrive(tm1637.clkPin, false);
  pinMode(tm1637.dioPin, INPUT_PULLUP);
  delayMicroseconds(TM_DELAY_US);
  tmDrive(tm1637.clkPin, true);
  delayMicroseconds(TM_DELAY_US);
  bool ack = digitalRead(tm1637.dioPin) == LOW;
  tmDrive(tm1637.clkPin, false);
  tmDrive(tm1637.dioPin, false);
  return ack;
}

uint8_t digitSegments(uint8_t digit) {
  static const uint8_t table[10] = {
    0x3F, 0x06, 0x5B, 0x4F, 0x66,
    0x6D, 0x7D, 0x07, 0x7F, 0x6F
  };
  return digit < 10 ? table[digit] : 0x00;
}

void tmWriteSegments(const uint8_t segments[4]) {
  if (!tm1637.configured) return;
  tmStart();
  tmWriteByte(0x40);  // automatic address increment
  tmStop();

  tmStart();
  tmWriteByte(0xC0);
  for (uint8_t i = 0; i < 4; ++i) tmWriteByte(segments[i]);
  tmStop();

  tmStart();
  tmWriteByte(static_cast<uint8_t>(0x88 | (tm1637.brightness & 0x07)));
  tmStop();
}

void tmShowDashes() {
  const uint8_t dash[4] = {0x40, 0x40, 0x40, 0x40};
  tmWriteSegments(dash);
}

void tmBlank() {
  const uint8_t blank[4] = {0, 0, 0, 0};
  tmWriteSegments(blank);
}

void tmShowTenths(int tenths) {
  if (!tm1637.configured) return;
  if (tenths < 0 || tenths > 9999) {
    tmShowDashes();
    return;
  }
  // Voltage display is right-aligned. 281 becomes " 28.1" with the decimal
  // point after the tens-of-volts digit.
  int whole = tenths / 10;
  uint8_t decimal = static_cast<uint8_t>(tenths % 10);
  uint8_t segments[4] = {0, 0, 0, 0};
  if (whole >= 100) {
    segments[0] = digitSegments(static_cast<uint8_t>((whole / 100) % 10));
    segments[1] = digitSegments(static_cast<uint8_t>((whole / 10) % 10));
    segments[2] = digitSegments(static_cast<uint8_t>(whole % 10)) | 0x80;
    segments[3] = digitSegments(decimal);
  } else if (whole >= 10) {
    segments[0] = 0;
    segments[1] = digitSegments(static_cast<uint8_t>((whole / 10) % 10));
    segments[2] = digitSegments(static_cast<uint8_t>(whole % 10)) | 0x80;
    segments[3] = digitSegments(decimal);
  } else {
    segments[0] = 0;
    segments[1] = 0;
    segments[2] = digitSegments(static_cast<uint8_t>(whole % 10)) | 0x80;
    segments[3] = digitSegments(decimal);
  }
  tmWriteSegments(segments);
}

bool configureTm1637(uint8_t clkPin, uint8_t dioPin, uint8_t brightness) {
  if (clkPin < FIRST_PIN || clkPin > LAST_PIN || dioPin < FIRST_PIN || dioPin > LAST_PIN || clkPin == dioPin) {
    sendError("TM1637_BAD_PINS");
    return false;
  }
  if (pins[clkPin].role != ROLE_NONE || pins[dioPin].role != ROLE_NONE) {
    sendError("TM1637_PIN_BUSY");
    return false;
  }
  tm1637.configured = true;
  tm1637.clkPin = clkPin;
  tm1637.dioPin = dioPin;
  tm1637.brightness = constrain(brightness, 0, 7);
  pins[clkPin].role = ROLE_PERIPHERAL;
  pins[dioPin].role = ROLE_PERIPHERAL;
  tmDrive(clkPin, true);
  tmDrive(dioPin, true);
  tmShowDashes();
  sendBody("OL1|ACK|TM1637_CFG");
  return true;
}

void releaseTm1637() {
  if (!tm1637.configured) return;
  tmBlank();
  pinMode(tm1637.clkPin, INPUT);
  digitalWrite(tm1637.clkPin, LOW);
  pinMode(tm1637.dioPin, INPUT);
  digitalWrite(tm1637.dioPin, LOW);
  tm1637.configured = false;
}

// ---------------- Core pin state ----------------

void safeAllPins() {
  running = false;
  learnInputs = false;
  learnAnalog = false;
  releaseTm1637();
  for (uint8_t pin = FIRST_PIN; pin <= LAST_PIN; ++pin) {
    pinMode(pin, INPUT);
    digitalWrite(pin, LOW);
    pins[pin].role = ROLE_NONE;
    pins[pin].approvedOutput = false;
    pins[pin].activeLow = false;
    pins[pin].raw = digitalRead(pin);
    pins[pin].stable = pins[pin].raw;
    pins[pin].debounceMs = 35;
    pins[pin].lastRawChange = millis();
    pins[pin].pulseUntil = 0;
    pins[pin].analogValue = 0;
    pins[pin].lastAnalogReport = 0;
  }
}

void loadIdentity() {
  EEPROM.get(0, identity);
  if (identity.magic != IDENTITY_MAGIC) {
    identity.magic = IDENTITY_MAGIC;
    strncpy(identity.uuid, "UNSET", sizeof(identity.uuid));
    strncpy(identity.name, "UNASSIGNED", sizeof(identity.name));
    identity.uuid[sizeof(identity.uuid) - 1] = '\0';
    identity.name[sizeof(identity.name) - 1] = '\0';
  }
}

void saveIdentity(const char* uuid, const char* name) {
  identity.magic = IDENTITY_MAGIC;
  strncpy(identity.uuid, uuid, sizeof(identity.uuid));
  strncpy(identity.name, name, sizeof(identity.name));
  identity.uuid[sizeof(identity.uuid) - 1] = '\0';
  identity.name[sizeof(identity.name) - 1] = '\0';
  EEPROM.put(0, identity);
}

bool verifyAndStripChecksum(char* line) {
  char* lastSeparator = strrchr(line, '|');
  if (!lastSeparator || strlen(lastSeparator + 1) != 2) return false;
  char* end = nullptr;
  unsigned long parsed = strtoul(lastSeparator + 1, &end, 16);
  if (!end || *end != '\0' || parsed > 0xFF) return false;
  uint8_t supplied = static_cast<uint8_t>(parsed);
  *lastSeparator = '\0';
  return checksumBody(line) == supplied;
}

bool configurePin(uint8_t pin, char mode, bool activeLow, uint16_t debounceMs) {
  if (pin < FIRST_PIN || pin > LAST_PIN) return false;
  if (pins[pin].role == ROLE_PERIPHERAL) return false;
  pins[pin].activeLow = activeLow;
  pins[pin].debounceMs = debounceMs;
  pins[pin].approvedOutput = false;
  pins[pin].pulseUntil = 0;
  if (mode == 'I') {
    pins[pin].role = ROLE_INPUT;
    pinMode(pin, INPUT_PULLUP);
    pins[pin].raw = digitalRead(pin);
    pins[pin].stable = pins[pin].raw;
    return true;
  }
  if (mode == 'A' && pin >= 54) {
    pins[pin].role = ROLE_ANALOG;
    pinMode(pin, INPUT);
    pins[pin].analogValue = analogRead(pin - 54);
    return true;
  }
  if (mode == 'O') {
    pins[pin].role = ROLE_OUTPUT;
    pinMode(pin, OUTPUT);
    setPhysicalOutput(pin, false);
    return true;
  }
  return false;
}

void handleCommand(char* line) {
  if (!verifyAndStripChecksum(line)) return;
  char* prefix = strtok(line, "|");
  char* command = strtok(nullptr, "|");
  if (!prefix || strcmp(prefix, "OL1") != 0 || !command) return;

  if (strcmp(command, "HELLO") == 0) {
    sendIdent();
  } else if (strcmp(command, "SET_ID") == 0) {
    char* uuid = strtok(nullptr, "|");
    char* name = strtok(nullptr, "|");
    if (uuid && name && strlen(uuid) <= 16 && strlen(name) <= 32) {
      saveIdentity(uuid, name);
      sendIdent();
    } else {
      sendError("BAD_IDENTITY");
    }
  } else if (strcmp(command, "SAFE") == 0) {
    safeAllPins();
    sendBody("OL1|ACK|SAFE");
  } else if (strcmp(command, "CONFIG") == 0) {
    char* pinText = strtok(nullptr, "|");
    char* modeText = strtok(nullptr, "|");
    char* activeText = strtok(nullptr, "|");
    char* debounceText = strtok(nullptr, "|");
    if (pinText && modeText && activeText && debounceText) {
      uint8_t pin = static_cast<uint8_t>(atoi(pinText));
      if (!configurePin(pin, modeText[0], atoi(activeText) != 0, static_cast<uint16_t>(atoi(debounceText)))) {
        sendError("CONFIG_REJECTED");
      }
    }
  } else if (strcmp(command, "TM1637_CFG") == 0) {
    char* clkText = strtok(nullptr, "|");
    char* dioText = strtok(nullptr, "|");
    char* brightText = strtok(nullptr, "|");
    if (!clkText || !dioText || !brightText) {
      sendError("TM1637_BAD_CFG");
    } else {
      configureTm1637(
        static_cast<uint8_t>(atoi(clkText)),
        static_cast<uint8_t>(atoi(dioText)),
        static_cast<uint8_t>(atoi(brightText))
      );
    }
  } else if (strcmp(command, "TM1637_VALUE") == 0) {
    char* valueText = strtok(nullptr, "|");
    if (!tm1637.configured || !valueText) {
      sendError("TM1637_NOT_READY");
    } else {
      tmShowTenths(atoi(valueText));
    }
  } else if (strcmp(command, "TM1637_DASH") == 0) {
    if (tm1637.configured) tmShowDashes();
  } else if (strcmp(command, "RUN") == 0) {
    running = true;
    learnInputs = false;
    learnAnalog = false;
    for (uint8_t pin = FIRST_PIN; pin <= LAST_PIN; ++pin) {
      if (pins[pin].role == ROLE_INPUT) sendDigital(pin, digitalRead(pin));
      if (pins[pin].role == ROLE_ANALOG) sendAnalog(pin, analogRead(pin - 54));
    }
    sendBody("OL1|ACK|RUN");
  } else if (strcmp(command, "SNAPSHOT") == 0) {
    for (uint8_t pin = FIRST_PIN; pin <= LAST_PIN; ++pin) {
      if (pins[pin].role == ROLE_INPUT) sendDigital(pin, digitalRead(pin));
      if (pins[pin].role == ROLE_ANALOG) sendAnalog(pin, analogRead(pin - 54));
    }
    sendBody("OL1|ACK|SNAPSHOT");
  } else if (strcmp(command, "LEARN_IN") == 0) {
    char* enabled = strtok(nullptr, "|");
    learnInputs = enabled && atoi(enabled) != 0;
    for (uint8_t pin = FIRST_PIN; pin <= LAST_PIN; ++pin) {
      if (pins[pin].role != ROLE_NONE) continue;
      if (learnInputs) {
        pinMode(pin, INPUT_PULLUP);
        pins[pin].raw = digitalRead(pin);
        pins[pin].stable = pins[pin].raw;
        pins[pin].lastRawChange = millis();
      } else {
        pinMode(pin, INPUT);
        digitalWrite(pin, LOW);
      }
    }
    sendBody(learnInputs ? "OL1|ACK|LEARN_IN|1" : "OL1|ACK|LEARN_IN|0");
  } else if (strcmp(command, "LEARN_ANALOG") == 0) {
    char* enabled = strtok(nullptr, "|");
    learnAnalog = enabled && atoi(enabled) != 0;
    for (uint8_t pin = 54; pin <= LAST_PIN; ++pin) {
      if (pins[pin].role == ROLE_NONE || pins[pin].role == ROLE_ANALOG) {
        pins[pin].analogValue = analogRead(pin - 54);
        pins[pin].lastAnalogReport = 0;
      }
    }
    sendBody(learnAnalog ? "OL1|ACK|LEARN_ANALOG|1" : "OL1|ACK|LEARN_ANALOG|0");
  } else if (strcmp(command, "APPROVE_OUT") == 0) {
    char* pinText = strtok(nullptr, "|");
    if (pinText) {
      uint8_t pin = static_cast<uint8_t>(atoi(pinText));
      if (pin <= LAST_PIN && pins[pin].role == ROLE_OUTPUT) pins[pin].approvedOutput = true;
    }
  } else if (strcmp(command, "SET") == 0) {
    char* pinText = strtok(nullptr, "|");
    char* valueText = strtok(nullptr, "|");
    if (pinText && valueText) {
      uint8_t pin = static_cast<uint8_t>(atoi(pinText));
      if (pin <= LAST_PIN && pins[pin].role == ROLE_OUTPUT && pins[pin].approvedOutput) {
        setPhysicalOutput(pin, atoi(valueText) != 0);
      }
    }
  } else if (strcmp(command, "PULSE") == 0) {
    char* pinText = strtok(nullptr, "|");
    char* durationText = strtok(nullptr, "|");
    if (pinText && durationText) {
      uint8_t pin = static_cast<uint8_t>(atoi(pinText));
      uint16_t duration = constrain(atoi(durationText), 50, 2000);
      if (pin <= LAST_PIN && pins[pin].role == ROLE_OUTPUT && pins[pin].approvedOutput) {
        setPhysicalOutput(pin, true);
        pins[pin].pulseUntil = millis() + duration;
      }
    }
  } else {
    sendError("UNKNOWN_COMMAND");
  }
}

void readSerial() {
  while (Serial.available()) {
    char value = static_cast<char>(Serial.read());
    if (value == '\n' || value == '\r') {
      if (lineLength > 0) {
        lineBuffer[lineLength] = '\0';
        handleCommand(lineBuffer);
        lineLength = 0;
      }
    } else if (lineLength < sizeof(lineBuffer) - 1) {
      lineBuffer[lineLength++] = value;
    } else {
      lineLength = 0;
      sendError("LINE_TOO_LONG");
    }
  }
}

void scanDigitalInputs(unsigned long now) {
  for (uint8_t pin = FIRST_PIN; pin <= LAST_PIN; ++pin) {
    bool shouldScan = pins[pin].role == ROLE_INPUT || (learnInputs && pins[pin].role == ROLE_NONE);
    if (!shouldScan) continue;
    bool raw = digitalRead(pin);
    if (raw != pins[pin].raw) {
      pins[pin].raw = raw;
      pins[pin].lastRawChange = now;
    }
    if (raw != pins[pin].stable && now - pins[pin].lastRawChange >= pins[pin].debounceMs) {
      pins[pin].stable = raw;
      sendDigital(pin, raw);
    }
  }
}

void scanAnalogInputs(unsigned long now) {
  for (uint8_t pin = 54; pin <= LAST_PIN; ++pin) {
    bool configuredInput = running && pins[pin].role == ROLE_ANALOG;
    bool learningCandidate = learnAnalog && pins[pin].role == ROLE_NONE;
    if ((!configuredInput && !learningCandidate) || now - pins[pin].lastAnalogReport < ANALOG_REPORT_MS) continue;
    int value = analogRead(pin - 54);
    if (abs(value - pins[pin].analogValue) >= 3) {
      pins[pin].analogValue = value;
      sendAnalog(pin, value);
    }
    pins[pin].lastAnalogReport = now;
  }
}

void servicePulses(unsigned long now) {
  for (uint8_t pin = FIRST_PIN; pin <= LAST_PIN; ++pin) {
    if (pins[pin].pulseUntil && static_cast<long>(now - pins[pin].pulseUntil) >= 0) {
      setPhysicalOutput(pin, false);
      pins[pin].pulseUntil = 0;
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  loadIdentity();
  safeAllPins();
  delay(40);
  sendIdent();
}

void loop() {
  readSerial();
  unsigned long now = millis();
  scanDigitalInputs(now);
  scanAnalogInputs(now);
  servicePulses(now);
  if (now - lastHeartbeat >= HEARTBEAT_MS) {
    char body[48];
    snprintf(body, sizeof(body), "OL1|HEARTBEAT|%lu", now);
    sendBody(body);
    lastHeartbeat = now;
  }
}
