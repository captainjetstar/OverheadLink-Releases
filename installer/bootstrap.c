#define COBJMACROS

#include <windows.h>
#include <commctrl.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <objbase.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#define APP_NAME L"OverheadLink"
#define APP_VERSION L"0.3.5"
#define PATH_CAPACITY 4096
#define COPY_BUFFER_SIZE (1024 * 1024)

static const unsigned char TRAILER_MAGIC[8] = {'O', 'H', 'L', 'N', 'K', '0', '3', '!'};
static const unsigned char PACKAGE_MAGIC[8] = {'O', 'H', 'P', 'A', 'C', 'K', '2', '!'};

static HWND setup_window = NULL;
static HWND status_label = NULL;
static HWND progress_bar = NULL;
static HFONT title_font = NULL;
static HFONT body_font = NULL;
static HBRUSH window_brush = NULL;
static BOOL setup_complete = FALSE;

static void pump_messages(void) {
    MSG message;
    while (PeekMessageW(&message, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
}

static LRESULT CALLBACK setup_window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    switch (message) {
        case WM_CLOSE:
            if (setup_complete) DestroyWindow(window);
            return 0;
        case WM_CTLCOLORSTATIC: {
            HDC dc = (HDC)wparam;
            SetBkMode(dc, TRANSPARENT);
            SetTextColor(dc, RGB(225, 233, 240));
            return (LRESULT)window_brush;
        }
        case WM_DESTROY:
            setup_window = NULL;
            return 0;
        default:
            return DefWindowProcW(window, message, wparam, lparam);
    }
}

static BOOL create_setup_window(HINSTANCE instance) {
    INITCOMMONCONTROLSEX controls = {sizeof(controls), ICC_PROGRESS_CLASS};
    InitCommonControlsEx(&controls);

    window_brush = CreateSolidBrush(RGB(17, 24, 32));
    WNDCLASSW window_class = {0};
    window_class.lpfnWndProc = setup_window_proc;
    window_class.hInstance = instance;
    window_class.hCursor = LoadCursorW(NULL, IDC_ARROW);
    window_class.hIcon = LoadIconW(instance, MAKEINTRESOURCEW(101));
    if (!window_class.hIcon) window_class.hIcon = LoadIconW(NULL, IDI_APPLICATION);
    window_class.hbrBackground = window_brush;
    window_class.lpszClassName = L"OverheadLinkSetupWindow";
    if (!RegisterClassW(&window_class) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) return FALSE;

    RECT work_area;
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work_area, 0);
    const int width = 560;
    const int height = 230;
    const int x = work_area.left + ((work_area.right - work_area.left) - width) / 2;
    const int y = work_area.top + ((work_area.bottom - work_area.top) - height) / 2;
    setup_window = CreateWindowExW(
        WS_EX_APPWINDOW,
        window_class.lpszClassName,
        L"OverheadLink automatic setup",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
        x,
        y,
        width,
        height,
        NULL,
        NULL,
        instance,
        NULL
    );
    if (!setup_window) return FALSE;

    title_font = CreateFontW(
        -26, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI"
    );
    body_font = CreateFontW(
        -17, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI"
    );

    HWND title = CreateWindowExW(
        0, L"STATIC", L"OVERHEADLINK", WS_CHILD | WS_VISIBLE,
        28, 24, 490, 38, setup_window, NULL, instance, NULL
    );
    SendMessageW(title, WM_SETFONT, (WPARAM)title_font, TRUE);

    status_label = CreateWindowExW(
        0, L"STATIC", L"Preparing the application…", WS_CHILD | WS_VISIBLE,
        30, 77, 490, 48, setup_window, NULL, instance, NULL
    );
    SendMessageW(status_label, WM_SETFONT, (WPARAM)body_font, TRUE);

    progress_bar = CreateWindowExW(
        0, PROGRESS_CLASSW, NULL, WS_CHILD | WS_VISIBLE | PBS_SMOOTH,
        30, 137, 490, 22, setup_window, NULL, instance, NULL
    );
    SendMessageW(progress_bar, PBM_SETRANGE, 0, MAKELPARAM(0, 100));
    SendMessageW(progress_bar, PBM_SETBARCOLOR, 0, RGB(246, 163, 59));

    HWND note = CreateWindowExW(
        0, L"STATIC", L"No administrator access or separate downloads are needed.", WS_CHILD | WS_VISIBLE,
        30, 169, 490, 26, setup_window, NULL, instance, NULL
    );
    SendMessageW(note, WM_SETFONT, (WPARAM)body_font, TRUE);

    ShowWindow(setup_window, SW_SHOW);
    UpdateWindow(setup_window);
    pump_messages();
    return TRUE;
}

static void set_setup_status(const wchar_t *text, int progress) {
    if (status_label) SetWindowTextW(status_label, text);
    if (progress_bar) SendMessageW(progress_bar, PBM_SETPOS, (WPARAM)progress, 0);
    pump_messages();
}

static void cleanup_setup_window(void) {
    setup_complete = TRUE;
    if (setup_window) DestroyWindow(setup_window);
    if (title_font) DeleteObject(title_font);
    if (body_font) DeleteObject(body_font);
    if (window_brush) DeleteObject(window_brush);
    title_font = NULL;
    body_font = NULL;
    window_brush = NULL;
}

static void show_error(const wchar_t *heading, const wchar_t *detail) {
    wchar_t message[2048];
    _snwprintf(message, 2047, L"%ls\n\n%ls", heading, detail);
    message[2047] = L'\0';
    MessageBoxW(setup_window, message, L"OverheadLink setup", MB_OK | MB_ICONERROR);
}

static BOOL path_join(wchar_t *output, size_t capacity, const wchar_t *left, const wchar_t *right) {
    const size_t left_length = wcslen(left);
    const size_t right_length = wcslen(right);
    const BOOL separator_needed = left_length > 0 && left[left_length - 1] != L'\\' && left[left_length - 1] != L'/';
    if (left_length + right_length + (separator_needed ? 2 : 1) > capacity) return FALSE;
    wcscpy(output, left);
    if (separator_needed) wcscat(output, L"\\");
    wcscat(output, right);
    return TRUE;
}

static BOOL paths_equal(const wchar_t *first, const wchar_t *second) {
    wchar_t first_full[PATH_CAPACITY];
    wchar_t second_full[PATH_CAPACITY];
    if (!GetFullPathNameW(first, PATH_CAPACITY, first_full, NULL)) return FALSE;
    if (!GetFullPathNameW(second, PATH_CAPACITY, second_full, NULL)) return FALSE;
    return _wcsicmp(first_full, second_full) == 0;
}

static BOOL ensure_directory(const wchar_t *path) {
    wchar_t partial[PATH_CAPACITY];
    const size_t length = wcslen(path);
    if (length == 0 || length >= PATH_CAPACITY) return FALSE;
    wcscpy(partial, path);
    for (size_t index = 3; index < length; ++index) {
        if (partial[index] == L'\\' || partial[index] == L'/') {
            const wchar_t saved = partial[index];
            partial[index] = L'\0';
            if (!CreateDirectoryW(partial, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) return FALSE;
            partial[index] = saved;
        }
    }
    return CreateDirectoryW(partial, NULL) || GetLastError() == ERROR_ALREADY_EXISTS;
}

static BOOL file_exists(const wchar_t *path) {
    const DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

static BOOL marker_matches(const wchar_t *path) {
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return FALSE;
    char value[32] = {0};
    DWORD read = 0;
    const BOOL ok = ReadFile(file, value, sizeof(value) - 1, &read, NULL);
    CloseHandle(file);
    return ok && strncmp(value, "0.3.5", 5) == 0;
}

static BOOL write_marker(const wchar_t *path) {
    HANDLE file = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return FALSE;
    static const char value[] = "0.3.5\r\n";
    DWORD written = 0;
    const BOOL ok = WriteFile(file, value, (DWORD)(sizeof(value) - 1), &written, NULL) && written == sizeof(value) - 1;
    CloseHandle(file);
    return ok;
}

static BOOL read_exact(HANDLE file, void *buffer, DWORD size) {
    unsigned char *cursor = (unsigned char *)buffer;
    DWORD remaining = size;
    while (remaining > 0) {
        DWORD received = 0;
        if (!ReadFile(file, cursor, remaining, &received, NULL) || received == 0) return FALSE;
        cursor += received;
        remaining -= received;
    }
    return TRUE;
}

static uint16_t read_u16_le(const unsigned char *bytes) {
    return (uint16_t)bytes[0] | ((uint16_t)bytes[1] << 8);
}

static uint32_t read_u32_le(const unsigned char *bytes) {
    return (uint32_t)bytes[0]
        | ((uint32_t)bytes[1] << 8)
        | ((uint32_t)bytes[2] << 16)
        | ((uint32_t)bytes[3] << 24);
}

static uint64_t read_u64_le(const unsigned char *bytes) {
    uint64_t value = 0;
    for (int index = 7; index >= 0; --index) value = (value << 8) | bytes[index];
    return value;
}

typedef struct Sha256State {
    BCRYPT_ALG_HANDLE algorithm;
    BCRYPT_HASH_HANDLE hash;
    PUCHAR object;
    DWORD object_length;
} Sha256State;

static BOOL sha256_begin(Sha256State *state) {
    ZeroMemory(state, sizeof(*state));
    if (BCryptOpenAlgorithmProvider(&state->algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0) != 0) return FALSE;
    DWORD returned = 0;
    if (BCryptGetProperty(
            state->algorithm,
            BCRYPT_OBJECT_LENGTH,
            (PUCHAR)&state->object_length,
            sizeof(state->object_length),
            &returned,
            0
        ) != 0) {
        BCryptCloseAlgorithmProvider(state->algorithm, 0);
        state->algorithm = NULL;
        return FALSE;
    }
    state->object = (PUCHAR)HeapAlloc(GetProcessHeap(), 0, state->object_length);
    if (!state->object) {
        BCryptCloseAlgorithmProvider(state->algorithm, 0);
        state->algorithm = NULL;
        return FALSE;
    }
    if (BCryptCreateHash(state->algorithm, &state->hash, state->object, state->object_length, NULL, 0, 0) != 0) {
        HeapFree(GetProcessHeap(), 0, state->object);
        BCryptCloseAlgorithmProvider(state->algorithm, 0);
        ZeroMemory(state, sizeof(*state));
        return FALSE;
    }
    return TRUE;
}

static BOOL sha256_update(Sha256State *state, unsigned char *data, DWORD size) {
    return BCryptHashData(state->hash, data, size, 0) == 0;
}

static BOOL sha256_finish(Sha256State *state, unsigned char output[32]) {
    return BCryptFinishHash(state->hash, output, 32, 0) == 0;
}

static void sha256_cleanup(Sha256State *state) {
    if (state->hash) BCryptDestroyHash(state->hash);
    if (state->object) HeapFree(GetProcessHeap(), 0, state->object);
    if (state->algorithm) BCryptCloseAlgorithmProvider(state->algorithm, 0);
    ZeroMemory(state, sizeof(*state));
}

static BOOL relative_path_is_safe(const wchar_t *path) {
    if (!path[0] || path[0] == L'\\' || path[0] == L'/' || wcschr(path, L':')) return FALSE;
    const wchar_t *component = path;
    for (const wchar_t *cursor = path;; ++cursor) {
        if (*cursor == L'\\' || *cursor == L'/' || *cursor == L'\0') {
            const size_t component_length = (size_t)(cursor - component);
            if (component_length == 0) return FALSE;
            if (component_length == 1 && component[0] == L'.') return FALSE;
            if (component_length == 2 && component[0] == L'.' && component[1] == L'.') return FALSE;
            if (*cursor == L'\0') break;
            component = cursor + 1;
        }
    }
    return TRUE;
}

static BOOL ensure_parent_directory(const wchar_t *full_path, size_t root_length) {
    wchar_t partial[PATH_CAPACITY];
    const size_t length = wcslen(full_path);
    if (length >= PATH_CAPACITY) return FALSE;
    wcscpy(partial, full_path);
    for (size_t index = root_length + 1; index < length; ++index) {
        if (partial[index] == L'\\' || partial[index] == L'/') {
            const wchar_t saved = partial[index];
            partial[index] = L'\0';
            if (!CreateDirectoryW(partial, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) return FALSE;
            partial[index] = saved;
        }
    }
    return TRUE;
}

static BOOL extract_payload(const wchar_t *executable_path, const wchar_t *application_root) {
    HANDLE source = CreateFileW(
        executable_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE,
        NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL
    );
    if (source == INVALID_HANDLE_VALUE) return FALSE;

    LARGE_INTEGER file_size;
    if (!GetFileSizeEx(source, &file_size) || file_size.QuadPart < 28) {
        CloseHandle(source);
        return FALSE;
    }

    unsigned char trailer[16];
    LARGE_INTEGER trailer_offset;
    trailer_offset.QuadPart = file_size.QuadPart - 16;
    if (!SetFilePointerEx(source, trailer_offset, NULL, FILE_BEGIN) || !read_exact(source, trailer, sizeof(trailer))) {
        CloseHandle(source);
        return FALSE;
    }
    if (memcmp(trailer, TRAILER_MAGIC, 8) != 0) {
        CloseHandle(source);
        return FALSE;
    }
    const uint64_t package_size = read_u64_le(trailer + 8);
    if (package_size < 12 || package_size > (uint64_t)file_size.QuadPart - 16) {
        CloseHandle(source);
        return FALSE;
    }

    LARGE_INTEGER package_offset;
    package_offset.QuadPart = file_size.QuadPart - 16 - (LONGLONG)package_size;
    if (!SetFilePointerEx(source, package_offset, NULL, FILE_BEGIN)) {
        CloseHandle(source);
        return FALSE;
    }

    unsigned char header[12];
    if (!read_exact(source, header, sizeof(header)) || memcmp(header, PACKAGE_MAGIC, 8) != 0) {
        CloseHandle(source);
        return FALSE;
    }
    const uint32_t file_count = read_u32_le(header + 8);
    if (file_count == 0 || file_count > 2000) {
        CloseHandle(source);
        return FALSE;
    }

    if (!ensure_directory(application_root)) {
        CloseHandle(source);
        return FALSE;
    }
    unsigned char *copy_buffer = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, COPY_BUFFER_SIZE);
    if (!copy_buffer) {
        CloseHandle(source);
        return FALSE;
    }

    BOOL success = TRUE;
    for (uint32_t file_index = 0; file_index < file_count && success; ++file_index) {
        unsigned char metadata[42];
        if (!read_exact(source, metadata, sizeof(metadata))) {
            success = FALSE;
            break;
        }
        const uint16_t path_length = read_u16_le(metadata);
        const uint64_t content_length = read_u64_le(metadata + 2);
        const unsigned char *expected_hash = metadata + 10;
        if (path_length == 0 || path_length > 2048 || content_length > (uint64_t)1024 * 1024 * 1024) {
            success = FALSE;
            break;
        }

        char utf8_path[2049];
        if (!read_exact(source, utf8_path, path_length)) {
            success = FALSE;
            break;
        }
        utf8_path[path_length] = '\0';
        wchar_t relative_path[2049];
        const int converted = MultiByteToWideChar(
            CP_UTF8, MB_ERR_INVALID_CHARS, utf8_path, path_length,
            relative_path, (int)(sizeof(relative_path) / sizeof(relative_path[0]) - 1)
        );
        if (converted <= 0) {
            success = FALSE;
            break;
        }
        relative_path[converted] = L'\0';
        for (int index = 0; index < converted; ++index) {
            if (relative_path[index] == L'/') relative_path[index] = L'\\';
        }
        if (!relative_path_is_safe(relative_path)) {
            success = FALSE;
            break;
        }

        wchar_t target_path[PATH_CAPACITY];
        if (!path_join(target_path, PATH_CAPACITY, application_root, relative_path)
            || !ensure_parent_directory(target_path, wcslen(application_root))) {
            success = FALSE;
            break;
        }

        HANDLE target = CreateFileW(target_path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (target == INVALID_HANDLE_VALUE) {
            success = FALSE;
            break;
        }
        Sha256State hash_state;
        if (!sha256_begin(&hash_state)) {
            CloseHandle(target);
            DeleteFileW(target_path);
            success = FALSE;
            break;
        }

        uint64_t remaining = content_length;
        while (remaining > 0) {
            const DWORD chunk = remaining > COPY_BUFFER_SIZE ? COPY_BUFFER_SIZE : (DWORD)remaining;
            DWORD written = 0;
            if (!read_exact(source, copy_buffer, chunk)
                || !sha256_update(&hash_state, copy_buffer, chunk)
                || !WriteFile(target, copy_buffer, chunk, &written, NULL)
                || written != chunk) {
                success = FALSE;
                break;
            }
            remaining -= chunk;
        }
        unsigned char actual_hash[32];
        if (success && (!sha256_finish(&hash_state, actual_hash) || memcmp(actual_hash, expected_hash, 32) != 0)) {
            success = FALSE;
        }
        sha256_cleanup(&hash_state);
        CloseHandle(target);
        if (!success) DeleteFileW(target_path);
    }

    HeapFree(GetProcessHeap(), 0, copy_buffer);
    CloseHandle(source);
    return success;
}

static DWORD run_process_wait(
    const wchar_t *executable,
    const wchar_t *arguments,
    const wchar_t *working_directory
) {
    wchar_t command_line[PATH_CAPACITY * 3];
    if (arguments && arguments[0]) {
        _snwprintf(command_line, sizeof(command_line) / sizeof(command_line[0]) - 1, L"\"%ls\" %ls", executable, arguments);
    } else {
        _snwprintf(command_line, sizeof(command_line) / sizeof(command_line[0]) - 1, L"\"%ls\"", executable);
    }
    command_line[sizeof(command_line) / sizeof(command_line[0]) - 1] = L'\0';

    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = SW_HIDE;
    if (!CreateProcessW(
            executable, command_line, NULL, NULL, FALSE,
            CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
            NULL, working_directory, &startup, &process
        )) return 0xFFFFFFFFUL;

    for (;;) {
        const DWORD wait_result = WaitForSingleObject(process.hProcess, 100);
        pump_messages();
        if (wait_result == WAIT_OBJECT_0) break;
        if (wait_result == WAIT_FAILED) {
            CloseHandle(process.hThread);
            CloseHandle(process.hProcess);
            return 0xFFFFFFFFUL;
        }
    }
    DWORD exit_code = 0xFFFFFFFFUL;
    GetExitCodeProcess(process.hProcess, &exit_code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return exit_code;
}

static BOOL python_runtime_valid(const wchar_t *python_executable, const wchar_t *working_directory) {
    if (!file_exists(python_executable)) return FALSE;
    const wchar_t *check = L"-c \"import sys, tkinter; assert sys.version_info[:2] == (3, 12)\"";
    return run_process_wait(python_executable, check, working_directory) == 0;
}

static BOOL python_dependencies_valid(const wchar_t *python_executable, const wchar_t *working_directory) {
    const wchar_t *check = L"-c \"import tkinter, serial; assert serial.VERSION == '3.5'\"";
    return run_process_wait(python_executable, check, working_directory) == 0;
}

static BOOL launch_application(
    const wchar_t *pythonw_executable,
    const wchar_t *script_path,
    const wchar_t *working_directory
) {
    wchar_t command_line[PATH_CAPACITY * 2];
    _snwprintf(
        command_line, sizeof(command_line) / sizeof(command_line[0]) - 1,
        L"\"%ls\" \"%ls\"", pythonw_executable, script_path
    );
    command_line[sizeof(command_line) / sizeof(command_line[0]) - 1] = L'\0';
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = SW_SHOWNORMAL;
    if (!CreateProcessW(
            pythonw_executable, command_line, NULL, NULL, FALSE,
            CREATE_UNICODE_ENVIRONMENT, NULL, working_directory, &startup, &process
        )) return FALSE;
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return TRUE;
}

static BOOL create_shortcut(const wchar_t *target, const wchar_t *shortcut_path, const wchar_t *working_directory) {
    IShellLinkW *link = NULL;
    IPersistFile *persist = NULL;
    HRESULT result = CoCreateInstance(
        &CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER,
        &IID_IShellLinkW, (void **)&link
    );
    if (FAILED(result) || !link) return FALSE;
    result = IShellLinkW_SetPath(link, target);
    if (SUCCEEDED(result)) result = IShellLinkW_SetWorkingDirectory(link, working_directory);
    if (SUCCEEDED(result)) result = IShellLinkW_SetDescription(link, L"MSFS 2024 / Fenix A320 overhead panel controller");
    if (SUCCEEDED(result)) result = IShellLinkW_SetIconLocation(link, target, 0);
    if (SUCCEEDED(result)) result = IShellLinkW_QueryInterface(link, &IID_IPersistFile, (void **)&persist);
    if (SUCCEEDED(result) && persist) result = IPersistFile_Save(persist, shortcut_path, TRUE);
    if (persist) IPersistFile_Release(persist);
    IShellLinkW_Release(link);
    return SUCCEEDED(result);
}

static void create_user_shortcuts(const wchar_t *installed_launcher, const wchar_t *install_root) {
    wchar_t desktop[PATH_CAPACITY];
    wchar_t shortcut[PATH_CAPACITY];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_DESKTOPDIRECTORY | CSIDL_FLAG_CREATE, NULL, SHGFP_TYPE_CURRENT, desktop))
        && path_join(shortcut, PATH_CAPACITY, desktop, L"OverheadLink.lnk")) {
        create_shortcut(installed_launcher, shortcut, install_root);
    }

    wchar_t programs[PATH_CAPACITY];
    wchar_t menu_folder[PATH_CAPACITY];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_PROGRAMS | CSIDL_FLAG_CREATE, NULL, SHGFP_TYPE_CURRENT, programs))
        && path_join(menu_folder, PATH_CAPACITY, programs, L"OverheadLink")
        && ensure_directory(menu_folder)
        && path_join(shortcut, PATH_CAPACITY, menu_folder, L"OverheadLink.lnk")) {
        create_shortcut(installed_launcher, shortcut, install_root);
    }
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show_command) {
    (void)previous;
    (void)command_line;
    (void)show_command;

    HANDLE setup_mutex = CreateMutexW(NULL, TRUE, L"Local\\OverheadLink-Setup-v0.3.5");
    if (!setup_mutex || GetLastError() == ERROR_ALREADY_EXISTS) {
        MessageBoxW(NULL, L"OverheadLink is already starting. Please wait a moment.", APP_NAME, MB_OK | MB_ICONINFORMATION);
        if (setup_mutex) CloseHandle(setup_mutex);
        return 0;
    }

    wchar_t local_application_data[PATH_CAPACITY];
    if (FAILED(SHGetFolderPathW(
            NULL, CSIDL_LOCAL_APPDATA | CSIDL_FLAG_CREATE, NULL,
            SHGFP_TYPE_CURRENT, local_application_data
        ))) {
        show_error(L"Windows did not provide a local application-data folder.", L"Setup cannot continue.");
        CloseHandle(setup_mutex);
        return 1;
    }

    wchar_t install_root[PATH_CAPACITY];
    wchar_t application_root[PATH_CAPACITY];
    wchar_t runtime_root[PATH_CAPACITY];
    wchar_t installed_launcher[PATH_CAPACITY];
    wchar_t payload_marker[PATH_CAPACITY];
    wchar_t install_marker[PATH_CAPACITY];
    wchar_t python_installer[PATH_CAPACITY];
    wchar_t pyserial_wheel[PATH_CAPACITY];
    wchar_t python_executable[PATH_CAPACITY];
    wchar_t pythonw_executable[PATH_CAPACITY];
    wchar_t application_script[PATH_CAPACITY];
    wchar_t profile_path[PATH_CAPACITY];
    wchar_t self_path[PATH_CAPACITY];

    if (!path_join(install_root, PATH_CAPACITY, local_application_data, L"OverheadLink")
        || !path_join(application_root, PATH_CAPACITY, install_root, L"app")
        || !path_join(runtime_root, PATH_CAPACITY, install_root, L"runtime")
        || !path_join(installed_launcher, PATH_CAPACITY, install_root, L"OverheadLink.exe")
        || !path_join(payload_marker, PATH_CAPACITY, application_root, L"payload.version")
        || !path_join(install_marker, PATH_CAPACITY, install_root, L"install.version")
        || !path_join(python_installer, PATH_CAPACITY, application_root, L"vendor\\python-3.12.10-amd64.exe")
        || !path_join(pyserial_wheel, PATH_CAPACITY, application_root, L"vendor\\pyserial-3.5-py2.py3-none-any.whl")
        || !path_join(python_executable, PATH_CAPACITY, runtime_root, L"python.exe")
        || !path_join(pythonw_executable, PATH_CAPACITY, runtime_root, L"pythonw.exe")
        || !path_join(application_script, PATH_CAPACITY, application_root, L"run_overheadlink.py")
        || !path_join(profile_path, PATH_CAPACITY, application_root, L"profiles\\a320_fenix_overhead.json")
        || !GetModuleFileNameW(NULL, self_path, PATH_CAPACITY)) {
        show_error(L"An installation path was too long.", L"Move the executable to a shorter Windows user profile and try again.");
        CloseHandle(setup_mutex);
        return 1;
    }

    if (!ensure_directory(install_root)) {
        show_error(L"The OverheadLink application folder could not be created.", install_root);
        CloseHandle(setup_mutex);
        return 1;
    }

    if (!paths_equal(self_path, installed_launcher)) {
        CopyFileW(self_path, installed_launcher, FALSE);
    }
    const wchar_t *shortcut_target = file_exists(installed_launcher) ? installed_launcher : self_path;

    BOOL payload_ready = marker_matches(payload_marker)
        && file_exists(application_script)
        && file_exists(profile_path)
        && file_exists(python_installer)
        && file_exists(pyserial_wheel);
    BOOL runtime_ready = python_runtime_valid(python_executable, install_root);
    BOOL dependencies_ready = runtime_ready && python_dependencies_valid(python_executable, application_root);
    BOOL installation_ready = payload_ready && runtime_ready && dependencies_ready && marker_matches(install_marker);

    if (!installation_ready && !create_setup_window(instance)) {
        show_error(L"The setup window could not be opened.", L"Restart Windows and run OverheadLink again.");
        CloseHandle(setup_mutex);
        return 1;
    }

    if (!payload_ready) {
        set_setup_status(L"Unpacking OverheadLink and the hardware profiles…", 15);
        if (!extract_payload(self_path, application_root) || !write_marker(payload_marker)) {
            show_error(L"The embedded OverheadLink files could not be unpacked.", L"The executable may be incomplete. Download a fresh copy and try again.");
            cleanup_setup_window();
            CloseHandle(setup_mutex);
            return 1;
        }
        payload_ready = TRUE;
    }

    if (!runtime_ready) {
        set_setup_status(L"Installing the private Python runtime…", 42);
        wchar_t install_arguments[PATH_CAPACITY * 2];
        _snwprintf(
            install_arguments, sizeof(install_arguments) / sizeof(install_arguments[0]) - 1,
            L"/quiet InstallAllUsers=0 TargetDir=\"%ls\" Include_launcher=0 InstallLauncherAllUsers=0 "
            L"AssociateFiles=0 Shortcuts=0 PrependPath=0 Include_doc=0 Include_test=0 "
            L"Include_pip=1 Include_tcltk=1 Include_tools=0",
            runtime_root
        );
        install_arguments[sizeof(install_arguments) / sizeof(install_arguments[0]) - 1] = L'\0';
        const DWORD installer_result = run_process_wait(python_installer, install_arguments, application_root);
        if ((installer_result != 0 && installer_result != 3010)
            || !python_runtime_valid(python_executable, install_root)) {
            wchar_t detail[512];
            _snwprintf(detail, 511, L"The embedded Python installer returned code %lu.", installer_result);
            detail[511] = L'\0';
            show_error(L"The private runtime could not be installed.", detail);
            cleanup_setup_window();
            CloseHandle(setup_mutex);
            return 1;
        }
        runtime_ready = TRUE;
    }

    if (!dependencies_ready) {
        set_setup_status(L"Installing the USB serial support package…", 76);
        wchar_t pip_arguments[PATH_CAPACITY * 2];
        _snwprintf(
            pip_arguments, sizeof(pip_arguments) / sizeof(pip_arguments[0]) - 1,
            L"-m pip install --disable-pip-version-check --no-index --force-reinstall \"%ls\"",
            pyserial_wheel
        );
        pip_arguments[sizeof(pip_arguments) / sizeof(pip_arguments[0]) - 1] = L'\0';
        const DWORD pip_result = run_process_wait(python_executable, pip_arguments, application_root);
        if (pip_result != 0 || !python_dependencies_valid(python_executable, application_root)) {
            wchar_t detail[512];
            _snwprintf(detail, 511, L"The embedded PySerial installation returned code %lu.", pip_result);
            detail[511] = L'\0';
            show_error(L"USB serial support could not be installed.", detail);
            cleanup_setup_window();
            CloseHandle(setup_mutex);
            return 1;
        }
        dependencies_ready = TRUE;
    }

    set_setup_status(L"Creating shortcuts and starting OverheadLink…", 94);
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    create_user_shortcuts(shortcut_target, install_root);
    CoUninitialize();
    if (!write_marker(install_marker)) {
        show_error(L"Setup finished, but its completion marker could not be saved.", install_marker);
        cleanup_setup_window();
        CloseHandle(setup_mutex);
        return 1;
    }

    set_setup_status(L"Ready — opening the overhead controller.", 100);
    pump_messages();
    Sleep(250);
    cleanup_setup_window();

    if (!launch_application(pythonw_executable, application_script, application_root)) {
        show_error(L"OverheadLink was installed but could not be opened.", L"Run the executable again. Setup will verify and repair the private runtime automatically.");
        CloseHandle(setup_mutex);
        return 1;
    }

    ReleaseMutex(setup_mutex);
    CloseHandle(setup_mutex);
    return 0;
}
