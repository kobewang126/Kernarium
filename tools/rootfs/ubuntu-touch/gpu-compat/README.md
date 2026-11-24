# Guest Mesa compatibility

This temporary Linux arm64 library completes the Mir platform's GBM image
validation callbacks for the guest Mesa version pinned in `../sources.json`.
It uses a private GBM layout, so the graphics startup service verifies the
original guest libraries before Lomiri starts. It retains existing callbacks
and leaves unsupported object layouts untouched. The permanent replacement is
a Mesa Mir/MirRs platform initialization patch.

Build on Ubuntu 24.04 arm64 with CMake, Ninja and a C++20 compiler:

```sh
python3 tools/rootfs/ubuntu-touch/gpu-compat/build.py --output /path/to/artifact
```

The output contains the library and a receipt identifying its source inputs
and digest. `build-policy.py --gpu-compat` verifies both before packaging.
Toucharium selects it with `TOUCHARIUM_GPU_COMPAT_DIR`; its default is
`.build/toucharium/gpu-compat`. Source or pin changes require a rebuilt artifact.
The library runs inside the Linux guest and does not alter iOS libraries.
