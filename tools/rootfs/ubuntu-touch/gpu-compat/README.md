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
python3 tools/rootfs/ubuntu-touch/gpu-compat/embed.py --artifact /path/to/artifact
```

The output contains the library and a receipt identifying its source inputs
and digest. The image producer verifies both before installation into EROFS;
the full `build-policy.py --gpu-compat` mode also verifies them.
`../package.py` carries the prebuilt library and its receipt as compressed
data. It verifies and extracts the same ARM64 binary on either ARM64 or x86-64
Linux; users do not need a compiler. The embedded payload is generated only by
`embed.py`; `--check` verifies it against a built artifact. Corresponding
library source and build files remain in this directory. Source or pin changes
require rebuilding the artifact and regenerating the payload.
The library runs inside the Linux guest and does not alter iOS libraries.
