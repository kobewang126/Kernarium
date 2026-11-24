// SPDX-License-Identifier: GPL-2.0-or-later
// Temporary guest-only compatibility experiment for the pinned PDK Mesa build.
// The permanent fix belongs in Mesa's Mir platform callback initialization.
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <malloc.h>
#include <mutex>

namespace {
using Lookup = void* (*)(void*, void*, void*);
struct Entry { void* device{}; void* display{}; Lookup lookup{}; };
Entry entries[32];
unsigned entryCount{};
std::mutex entriesMutex;
Lookup lookupFor(void* display) {
    std::lock_guard lock(entriesMutex);
    for (unsigned i = 0; i < entryCount; ++i)
        if (entries[i].display == display) return entries[i].lookup;
    return nullptr;
}
unsigned char validate(void* image, void* display) {
    const auto lookup = lookupFor(display);
    return lookup && lookup(nullptr, image, display) != nullptr;
}
void* validated(void* image, void* display) {
    const auto lookup = lookupFor(display);
    return lookup ? lookup(nullptr, image, display) : nullptr;
}
void repair(void* display) {
    std::lock_guard lock(entriesMutex);
    for (unsigned i = 0; i < entryCount; ++i) {
        auto& entry = entries[i];
        if (entry.display || malloc_usable_size(entry.device) != 456) continue;
        // Exact layout of the pinned arm64 Mesa 24.0.9 gbm_dri_device.
        auto address = static_cast<unsigned char*>(entry.device) + 368;
        void* fields[4];
        std::memcpy(fields, address, sizeof(fields));
        if (fields[3] != display || !fields[0] || fields[1] || fields[2]) continue;
        entry.lookup = reinterpret_cast<Lookup>(fields[0]);
        entry.display = display;
        fields[1] = reinterpret_cast<void*>(&validate);
        fields[2] = reinterpret_cast<void*>(&validated);
        std::memcpy(address, fields, sizeof(fields));
        std::fprintf(stderr, "Toucharium: enabled Mir EGL image validation compatibility\n");
    }
}
}
extern "C" void* gbm_create_device(int fd) {
    static auto original = reinterpret_cast<void* (*)(int)>(
        dlsym(dlopen("libgbm.so.1", RTLD_LAZY), "gbm_create_device"));
    if (!original) return nullptr;
    void* device = original(fd);
    if (device) {
        std::lock_guard lock(entriesMutex);
        bool found = false;
        for (unsigned i = 0; i < entryCount; ++i) found |= entries[i].device == device;
        if (!found && entryCount < 32) entries[entryCount++].device = device;
    }
    return device;
}
extern "C" unsigned eglInitialize(void* display, int* major, int* minor) {
    static auto original = reinterpret_cast<unsigned (*)(void*, int*, int*)>(
        dlsym(dlopen("libEGL.so.1", RTLD_LAZY), "eglInitialize"));
    if (!original) return 0;
    const unsigned result = original(display, major, minor);
    if (result) repair(display);
    return result;
}

extern "C" void gbm_device_destroy(void* device) {
    static auto original = reinterpret_cast<void (*)(void*)>(
        dlsym(dlopen("libgbm.so.1", RTLD_LAZY), "gbm_device_destroy"));
    {
        std::lock_guard lock(entriesMutex);
        for (unsigned i = 0; i < entryCount; ++i) {
            if (entries[i].device == device) {
                entries[i] = entries[--entryCount];
                break;
            }
        }
    }
    if (original) original(device);
}
