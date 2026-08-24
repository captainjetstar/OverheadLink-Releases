#include <Adafruit_NeoPixel.h>
#include <EEPROM.h>

// OverheadLink COM21 backlighting Nano firmware v0.2.0
// Lights illuminate immediately at power-on and retain the last named preset.

static const char* FW_VERSION = "0.2.0";
static const uint8_t DATA_PIN = 6;
static const uint16_t LED_COUNT = 300;
static const uint32_t SETTINGS_MAGIC = 0x4F4C424CUL;  // OLBL

enum Preset : uint8_t { FULL_LIGHT = 0, HALF_DIM = 1, DAY_TIME_DIM = 2 };

struct StoredSettings {
  uint32_t magic;
  char uuid[17];
  char name[33];
  uint8_t brightness[3];
  uint8_t currentPreset;
  uint8_t red;
  uint8_t green;
  uint8_t blue;
};

Adafruit_NeoPixel strip(LED_COUNT, DATA_PIN, NEO_GRB + NEO_KHZ800);
StoredSettings settings;
char lineBuffer[150];
uint8_t lineLength = 0;
unsigned long lastHeartbeat = 0;

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

void sendIdent() {
  char body[120];
  snprintf(body, sizeof(body), "OL1|IDENT|NANO|%s|%s|%s", settings.uuid, settings.name, FW_VERSION);
  sendBody(body);
}

const char* presetToken(uint8_t preset) {
  if (preset == FULL_LIGHT) return "FULL_LIGHT";
  if (preset == HALF_DIM) return "HALF_DIM";
  return "DAY_TIME_DIM";
}

int presetFromToken(const char* token) {
  if (strcmp(token, "FULL_LIGHT") == 0) return FULL_LIGHT;
  if (strcmp(token, "HALF_DIM") == 0) return HALF_DIM;
  if (strcmp(token, "DAY_TIME_DIM") == 0) return DAY_TIME_DIM;
  return -1;
}

void saveSettings() {
  EEPROM.put(0, settings);
}

void loadSettings() {
  EEPROM.get(0, settings);
  if (settings.magic != SETTINGS_MAGIC) {
    settings.magic = SETTINGS_MAGIC;
    strncpy(settings.uuid, "BACKLIGHTNANO001", sizeof(settings.uuid));
    strncpy(settings.name, "BACKLIGHT-NANO", sizeof(settings.name));
    settings.uuid[sizeof(settings.uuid) - 1] = '\0';
    settings.name[sizeof(settings.name) - 1] = '\0';
    settings.brightness[FULL_LIGHT] = 255;
    settings.brightness[HALF_DIM] = 128;
    settings.brightness[DAY_TIME_DIM] = 180;
    settings.currentPreset = DAY_TIME_DIM;
    settings.red = 255;
    settings.green = 128;
    settings.blue = 0;
    saveSettings();
  }
  if (settings.currentPreset > DAY_TIME_DIM) settings.currentPreset = DAY_TIME_DIM;
}

void renderLights() {
  strip.setBrightness(settings.brightness[settings.currentPreset]);
  uint32_t colour = strip.Color(settings.red, settings.green, settings.blue);
  strip.fill(colour, 0, LED_COUNT);
  strip.show();
}

void reportPreset() {
  char body[70];
  snprintf(body, sizeof(body), "OL1|PRESET|%s|%u", presetToken(settings.currentPreset), settings.brightness[settings.currentPreset]);
  sendBody(body);
}

bool verifyAndStripChecksum(char* line) {
  char* lastSeparator = strrchr(line, '|');
  if (!lastSeparator || strlen(lastSeparator + 1) != 2) return false;
  uint8_t supplied = static_cast<uint8_t>(strtoul(lastSeparator + 1, nullptr, 16));
  *lastSeparator = '\0';
  return checksumBody(line) == supplied;
}

void handleCommand(char* line) {
  if (!verifyAndStripChecksum(line)) return;
  char* prefix = strtok(line, "|");
  char* command = strtok(nullptr, "|");
  if (!prefix || strcmp(prefix, "OL1") != 0 || !command) return;

  if (strcmp(command, "HELLO") == 0 || strcmp(command, "STATUS") == 0) {
    sendIdent();
    reportPreset();
  } else if (strcmp(command, "SET_ID") == 0) {
    char* uuid = strtok(nullptr, "|");
    char* name = strtok(nullptr, "|");
    if (uuid && name) {
      strncpy(settings.uuid, uuid, sizeof(settings.uuid));
      strncpy(settings.name, name, sizeof(settings.name));
      settings.uuid[sizeof(settings.uuid) - 1] = '\0';
      settings.name[sizeof(settings.name) - 1] = '\0';
      saveSettings();
      sendIdent();
    }
  } else if (strcmp(command, "PRESET") == 0) {
    char* token = strtok(nullptr, "|");
    char* brightnessText = strtok(nullptr, "|");
    if (token) {
      int preset = presetFromToken(token);
      if (preset >= 0) {
        settings.currentPreset = static_cast<uint8_t>(preset);
        if (brightnessText) settings.brightness[preset] = constrain(atoi(brightnessText), 0, 255);
        saveSettings();
        renderLights();
        reportPreset();
      }
    }
  } else if (strcmp(command, "BRIGHTNESS") == 0) {
    char* valueText = strtok(nullptr, "|");
    if (valueText) {
      settings.brightness[settings.currentPreset] = constrain(atoi(valueText), 0, 255);
      saveSettings();
      renderLights();
      reportPreset();
    }
  } else if (strcmp(command, "COLOR") == 0) {
    char* redText = strtok(nullptr, "|");
    char* greenText = strtok(nullptr, "|");
    char* blueText = strtok(nullptr, "|");
    if (redText && greenText && blueText) {
      settings.red = constrain(atoi(redText), 0, 255);
      settings.green = constrain(atoi(greenText), 0, 255);
      settings.blue = constrain(atoi(blueText), 0, 255);
      saveSettings();
      renderLights();
      sendBody("OL1|ACK|COLOR");
    }
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
    }
  }
}

void setup() {
  Serial.begin(115200);
  loadSettings();
  strip.begin();
  strip.clear();
  renderLights();  // Automatic illumination without waiting for the PC app.
  delay(40);
  sendIdent();
  reportPreset();
}

void loop() {
  readSerial();
  unsigned long now = millis();
  if (now - lastHeartbeat >= 1000) {
    char body[48];
    snprintf(body, sizeof(body), "OL1|HEARTBEAT|%lu", now);
    sendBody(body);
    lastHeartbeat = now;
  }
}
