#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#if defined(__x86_64__)
#define LOADER "ld-linux-x86-64.so.2"
#elif defined(__aarch64__)
#define LOADER "ld-linux-aarch64.so.1"
#else
#error unsupported Linux architecture
#endif

static char *append(const char *left, const char *right)
{
    size_t size = strlen(left) + strlen(right) + 1;
    char *result = malloc(size);
    if (result)
        snprintf(result, size, "%s%s", left, right);
    return result;
}

static char *command_path(const char *name)
{
    if (strchr(name, '/'))
        return realpath(name, NULL);

    const char *path = getenv("PATH");
    if (!path)
        path = "/bin:/usr/bin";
    while (1) {
        const char *end = strchr(path, ':');
        size_t length = end ? (size_t)(end - path) : strlen(path);
        char *candidate = malloc(length + strlen(name) + 3);
        if (!candidate)
            return NULL;
        if (length)
            snprintf(candidate, length + strlen(name) + 3, "%.*s/%s", (int)length, path, name);
        else
            snprintf(candidate, length + strlen(name) + 3, "./%s", name);
        if (access(candidate, X_OK) == 0) {
            char *resolved = realpath(candidate, NULL);
            free(candidate);
            if (resolved)
                return resolved;
        } else {
            free(candidate);
        }
        if (!end)
            break;
        path = end + 1;
    }
    return NULL;
}

int main(int argc, char **argv)
{
    char *resolved = command_path(argv[0]);
    if (!resolved) {
        perror("resolve PostgreSQL command");
        return 127;
    }
    char *public_path = strdup(resolved);
    char *name = strrchr(resolved, '/');
    if (!public_path || !name || !name[1]) {
        fputs("invalid PostgreSQL command path\n", stderr);
        return 127;
    }
    name = strdup(name + 1);
    char *bin = strrchr(resolved, '/');
    if (!name || !bin) {
        fputs("PostgreSQL command must be inside a bin directory\n", stderr);
        return 127;
    }
    *bin = '\0';
    bin = strrchr(resolved, '/');
    if (!bin) return 127;
    *bin = '\0';
    if (!resolved[0]) strcpy(resolved, "/");

    char *loader = append(resolved, "/lib/glibc/" LOADER);
    char *payload_dir = append(resolved, "/libexec/");
    char *payload = payload_dir ? append(payload_dir, name) : NULL;
    size_t library_length = strlen(resolved) * 3 + sizeof("/lib/glibc:/lib:/lib/runtime");
    char *library_path = malloc(library_length);
    char **arguments = calloc((size_t)argc + 6, sizeof(char *));
    if (!loader || !payload || !library_path || !arguments) {
        fputs("out of memory launching PostgreSQL command\n", stderr);
        return 127;
    }
    snprintf(library_path, library_length, "%s/lib/glibc:%s/lib:%s/lib/runtime",
             resolved, resolved, resolved);
    arguments[0] = loader;
    arguments[1] = "--argv0";
    arguments[2] = public_path;
    arguments[3] = "--library-path";
    arguments[4] = library_path;
    arguments[5] = payload;
    for (int index = 1; index < argc; index++)
        arguments[index + 5] = argv[index];
    execv(loader, arguments);
    perror("execute bundled PostgreSQL loader");
    return 127;
}
