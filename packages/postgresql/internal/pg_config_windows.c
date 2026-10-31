#include <windows.h>
#include <stdio.h>
#include <fcntl.h>
#include <io.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include "pg_config_paths.h"

static char *replace(const char *input, const char *before, const char *after)
{
    size_t oldlen = strlen(before), newlen = strlen(after), count = 0;
    const char *p = input, *found;
    char *result, *out;
    if (!oldlen) return _strdup(input);
    while ((found = strstr(p, before))) { count++; p = found + oldlen; }
    result = malloc(strlen(input) + count * newlen + 1);
    if (!result) exit(1);
    out = result; p = input;
    while ((found = strstr(p, before))) {
        memcpy(out, p, found - p); out += found - p;
        memcpy(out, after, newlen); out += newlen;
        p = found + oldlen;
    }
    strcpy(out, p);
    return result;
}

int wmain(int argc, wchar_t **argv)
{
    wchar_t executable[32768], command[32768], prefix[32768];
    char current[131072], dependencies[131072];
    HANDLE reader, writer;
    SECURITY_ATTRIBUTES security = {sizeof(security), NULL, TRUE};
    STARTUPINFOW startup = {sizeof(startup)};
    PROCESS_INFORMATION process;
    DWORD length, received, code;
    size_t capacity = 4096, used = 0;
    char *output = malloc(capacity), *updated;
    length = GetModuleFileNameW(NULL, executable, 32768);
    if (!length || length >= 32768 || !output) return 1;
    wcscpy_s(prefix, 32768, executable);
    *wcsrchr(prefix, L'\\') = 0;
    *wcsrchr(prefix, L'\\') = 0;
    swprintf_s(executable, 32768, L"%s\\bin\\pg_config.bin.exe", prefix);
    swprintf_s(command, 32768, L"\"%s\"", executable);
    for (int i = 1; i < argc; i++) {
        /* pg_config accepts option switches only; no shell or quoting is needed. */
        if (wcsspn(argv[i], L"-?abcdefghijklmnopqrstuvwxyz0123456789") != wcslen(argv[i])) return 1;
        if (wcscat_s(command, 32768, L" ") || wcscat_s(command, 32768, argv[i])) return 1;
    }
    if (!CreatePipe(&reader, &writer, &security, 0)) return 1;
    SetHandleInformation(reader, HANDLE_FLAG_INHERIT, 0);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdOutput = writer;
    startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    if (!CreateProcessW(executable, command, NULL, NULL, TRUE, 0, NULL, NULL, &startup, &process)) return 1;
    CloseHandle(writer);
    for (;;) {
        if (capacity - used < 2048) {
            capacity *= 2; updated = realloc(output, capacity);
            if (!updated) return 1;
            output = updated;
        }
        if (!ReadFile(reader, output + used, (DWORD)(capacity - used - 1), &received, NULL) || !received) break;
        used += received;
    }
    output[used] = 0;
    CloseHandle(reader);
    WaitForSingleObject(process.hProcess, INFINITE);
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hProcess); CloseHandle(process.hThread);
    if (!WideCharToMultiByte(CP_UTF8, 0, prefix, -1, current, sizeof(current), NULL, NULL)) return 1;
    for (char *p = current; *p; p++) if (*p == '\\') *p = '/';
    sprintf_s(dependencies, sizeof(dependencies), "%s/dependencies", current);
    updated = replace(output, ORIGINAL_DEPENDENCIES, dependencies); free(output); output = updated;
    updated = replace(output, ORIGINAL_POSTGRESQL, current); free(output); output = updated;
    /* Meson configuration strings can contain native separators as well. */
    updated = replace(output, ORIGINAL_DEPENDENCIES_NATIVE, dependencies); free(output); output = updated;
    updated = replace(output, ORIGINAL_POSTGRESQL_NATIVE, current); free(output);
    /* The captured upstream output already contains Windows CRLF sequences. */
    if (_setmode(_fileno(stdout), _O_BINARY) == -1) return 1;
    fputs(updated, stdout); free(updated);
    return (int)code;
}
