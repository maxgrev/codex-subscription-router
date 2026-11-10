#include <dlfcn.h>
#include <errno.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <mach/mach.h>
#include <malloc/malloc.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef FRAMEWORK_RELATIVE_PATH
#error "FRAMEWORK_RELATIVE_PATH must name the Codex Framework binary"
#endif
#ifndef PROFILE_NAME
#error "PROFILE_NAME must name the Application Support profile directory"
#endif

#define USER_DATA_SWITCH "--user-data-dir"
#define DELEGATING_ZONE_NAME "DelegatingDefaultZoneForPartitionAlloc"
#define PARTITION_ALLOC_ZONE_NAME "PartitionAlloc"
#define ZONE_VERSION 13

void abort_report_np(const char *fmt, ...);

typedef int (*ChromeMainFunction)(int, char **);

static void fatal(const char *format, ...) {
    char message[4096];
    va_list arguments;
    va_start(arguments, format);
    if (vsnprintf(message, sizeof(message), format, arguments) >= 0) {
        fputs(message, stderr);
        fputc('\n', stderr);
        abort_report_np("%s", message);
    }
    va_end(arguments);
    abort();
}

/* Mirrors partition_alloc::EarlyMallocZoneRegistration(): the framework's
   allocator shim expects this delegating zone to be the default zone before
   any other library allocates. */
static malloc_zone_t delegating_zone;
static malloc_introspection_t delegating_introspection;
static malloc_zone_t *system_zone;

static malloc_zone_t *current_default_zone(void) {
    vm_address_t *zones = NULL;
    unsigned int count = 0;
    if (malloc_get_all_zones(mach_task_self(), NULL, &zones, &count) != KERN_SUCCESS) {
        fatal("Cannot enumerate malloc zones.");
    }
    return (malloc_zone_t *)zones[0];
}

static void *zone_malloc(malloc_zone_t *zone, size_t size) {
    (void)zone;
    return system_zone->malloc(system_zone, size);
}

static void *zone_calloc(malloc_zone_t *zone, size_t count, size_t size) {
    (void)zone;
    return system_zone->calloc(system_zone, count, size);
}

static void *zone_valloc(malloc_zone_t *zone, size_t size) {
    (void)zone;
    return system_zone->valloc(system_zone, size);
}

static void *zone_realloc(malloc_zone_t *zone, void *pointer, size_t size) {
    (void)zone;
    return system_zone->realloc(system_zone, pointer, size);
}

static unsigned zone_batch_malloc(malloc_zone_t *zone, size_t size, void **results, unsigned requested) {
    (void)zone;
    return system_zone->batch_malloc(system_zone, size, results, requested);
}

static void *zone_memalign(malloc_zone_t *zone, size_t alignment, size_t size) {
    (void)zone;
    return system_zone->memalign(system_zone, alignment, size);
}

static size_t zone_size(malloc_zone_t *zone, const void *pointer) {
    (void)zone;
    (void)pointer;
    return 0;
}

static void zone_free(malloc_zone_t *zone, void *pointer) {
    (void)zone;
    system_zone->free(system_zone, pointer);
}

static void zone_free_definite_size(malloc_zone_t *zone, void *pointer, size_t size) {
    (void)zone;
    system_zone->free_definite_size(system_zone, pointer, size);
}

static void zone_batch_free(malloc_zone_t *zone, void **pointers, unsigned count) {
    (void)zone;
    system_zone->batch_free(system_zone, pointers, count);
}

static void zone_try_free_default(malloc_zone_t *zone, void *pointer) {
    (void)zone;
    system_zone->try_free_default(system_zone, pointer);
}

static size_t zone_pressure_relief(malloc_zone_t *zone, size_t goal) {
    (void)zone;
    (void)goal;
    return 0;
}

static kern_return_t introspect_enumerator(task_t task, void *context, unsigned type_mask,
                                           vm_address_t zone_address, memory_reader_t reader,
                                           vm_range_recorder_t recorder) {
    (void)task;
    (void)context;
    (void)type_mask;
    (void)zone_address;
    (void)reader;
    (void)recorder;
    return KERN_SUCCESS;
}

static size_t introspect_good_size(malloc_zone_t *zone, size_t size) {
    (void)zone;
    return system_zone->introspect->good_size(system_zone, size);
}

static boolean_t introspect_check(malloc_zone_t *zone) {
    (void)zone;
    return 1;
}

static void introspect_print(malloc_zone_t *zone, boolean_t verbose) {
    (void)zone;
    (void)verbose;
}

static void introspect_log(malloc_zone_t *zone, void *address) {
    (void)zone;
    (void)address;
}

static void introspect_noop(malloc_zone_t *zone) {
    (void)zone;
}

static void introspect_statistics(malloc_zone_t *zone, malloc_statistics_t *statistics) {
    (void)zone;
    (void)statistics;
}

static boolean_t introspect_false(malloc_zone_t *zone) {
    (void)zone;
    return 0;
}

static void introspect_discharge(malloc_zone_t *zone, void *memory) {
    (void)zone;
    (void)memory;
}

static void register_delegating_zone(void) {
    vm_address_t *zones = NULL;
    unsigned int count = 0;
    if (malloc_get_all_zones(mach_task_self(), NULL, &zones, &count) != KERN_SUCCESS) {
        fatal("Cannot enumerate malloc zones.");
    }
    for (unsigned int index = 0; index < count; index++) {
        const char *name = ((malloc_zone_t *)zones[index])->zone_name;
        if (name != NULL && strcmp(name, DELEGATING_ZONE_NAME) == 0) {
            fatal("The delegating default zone has unexpectedly already been registered.");
        }
        if (name != NULL && strcmp(name, PARTITION_ALLOC_ZONE_NAME) == 0) {
            fatal("The PartitionAlloc default zone has unexpectedly already been registered.");
        }
    }

    malloc_zone_t *purgeable_zone = malloc_default_purgeable_zone();
    system_zone = current_default_zone();

    delegating_zone.malloc = zone_malloc;
    delegating_zone.calloc = zone_calloc;
    delegating_zone.valloc = zone_valloc;
    delegating_zone.realloc = zone_realloc;
    delegating_zone.batch_malloc = zone_batch_malloc;
    delegating_zone.memalign = zone_memalign;
    delegating_zone.size = zone_size;
    delegating_zone.free = zone_free;
    delegating_zone.free_definite_size = zone_free_definite_size;
    delegating_zone.batch_free = zone_batch_free;
    if (system_zone->version >= ZONE_VERSION) {
        delegating_zone.try_free_default = zone_try_free_default;
    }
    delegating_zone.pressure_relief = zone_pressure_relief;

    delegating_introspection.enumerator = introspect_enumerator;
    delegating_introspection.good_size = introspect_good_size;
    delegating_introspection.check = introspect_check;
    delegating_introspection.print = introspect_print;
    delegating_introspection.log = introspect_log;
    delegating_introspection.force_lock = introspect_noop;
    delegating_introspection.force_unlock = introspect_noop;
    delegating_introspection.reinit_lock = introspect_noop;
    delegating_introspection.statistics = introspect_statistics;
    delegating_introspection.zone_locked = introspect_false;
    delegating_introspection.enable_discharge_checking = introspect_false;
    delegating_introspection.disable_discharge_checking = introspect_noop;
    delegating_introspection.discharge = introspect_discharge;

    delegating_zone.version = ZONE_VERSION;
    delegating_zone.introspect = &delegating_introspection;
    delegating_zone.zone_name = DELEGATING_ZONE_NAME;

    malloc_zone_register(&delegating_zone);
    malloc_zone_unregister(system_zone);
    malloc_zone_register(system_zone);
    malloc_zone_unregister(purgeable_zone);
    malloc_zone_register(purgeable_zone);

    if (current_default_zone() != &delegating_zone) {
        fatal("Failed to install the delegating zone as default.");
    }
}

static int has_user_data_switch(int argc, char **argv) {
    size_t length = strlen(USER_DATA_SWITCH);
    for (int index = 1; index < argc; index++) {
        if (strncmp(argv[index], USER_DATA_SWITCH, length) == 0 &&
            (argv[index][length] == '\0' || argv[index][length] == '=')) {
            return 1;
        }
    }
    return 0;
}

__attribute__((visibility("default"))) int main(int argc, char **argv) {
    register_delegating_zone();

    char executable[PATH_MAX];
    uint32_t size = sizeof(executable);
    if (_NSGetExecutablePath(executable, &size) != 0) {
        fatal("_NSGetExecutablePath: get path failed.");
    }
    const char *directory = dirname(executable);
    if (directory == NULL) {
        fatal("dirname %s: %s.", executable, strerror(errno));
    }
    char framework[PATH_MAX];
    if (snprintf(framework, sizeof(framework), "%s/%s", directory, FRAMEWORK_RELATIVE_PATH) >=
        (int)sizeof(framework)) {
        fatal("The framework path is too long.");
    }

    char **arguments = argv;
    int count = argc;
    char profile[PATH_MAX];
    if (!has_user_data_switch(argc, argv)) {
        const char *home = getenv("HOME");
        if (home == NULL || home[0] == '\0') {
            fatal("HOME is not set.");
        }
        if (snprintf(profile, sizeof(profile),
                     USER_DATA_SWITCH "=%s/Library/Application Support/" PROFILE_NAME,
                     home) >= (int)sizeof(profile)) {
            fatal("The profile path is too long.");
        }
        arguments = calloc((size_t)argc + 2, sizeof(*arguments));
        if (arguments == NULL) {
            fatal("Out of memory.");
        }
        arguments[0] = argv[0];
        arguments[1] = profile;
        for (int index = 1; index < argc; index++) {
            arguments[index + 1] = argv[index];
        }
        count = argc + 1;
    }

    void *library = dlopen(framework, RTLD_LAZY | RTLD_GLOBAL);
    if (library == NULL) {
        fatal("dlopen %s: %s.", framework, dlerror());
    }
    ChromeMainFunction chrome_main = (ChromeMainFunction)dlsym(library, "ChromeMain");
    if (chrome_main == NULL) {
        fatal("dlsym ChromeMain: %s.", dlerror());
    }
    exit(chrome_main(count, arguments));
}
