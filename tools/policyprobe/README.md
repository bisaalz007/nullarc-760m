# Read-only library-validation probe

This authored test host requests hardened runtime and library validation, reads
its own `csops(CS_OPS_STATUS)` flags, and loads a library with `dlopen`. It changes
no process flags or security settings and submits no GPU commands. Loading the
actual Metal bundle runs that bundle's constructors, but does not create a Metal
device. It is a loader diagnostic, not a WindowServer or acceleration test.

```sh
clang -arch x86_64 -mmacosx-version-min=15.0 -Wall -Wextra -Werror host.c -o policy-host
clang -arch x86_64 -mmacosx-version-min=15.0 -Wall -Wextra -Werror -dynamiclib library.c -o libpolicy-fixture.dylib
codesign --force --sign - --options runtime,library policy-host
codesign --force --sign - libpolicy-fixture.dylib
./policy-host "$PWD/libpolicy-fixture.dylib"
./policy-host /Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver --load-only
```

Without `--load-only`, the host additionally calls our fixture's exported function
and requires value `0x760`. Exit 1 means `dlopen` rejected the image; its actual
error is on stderr. Exit 4 means the fixture function/value was absent or wrong;
use `--load-only` for the real driver. Neither test calls Metal or changes display.

On the development Mac, the fixture is rejected with different Team IDs. On the
HP boot with the explicitly authorized upstream AMFI arguments, the same host
loads both the fixture and actual driver. HP process flags are `0x26012201`,
including PLATFORM_BINARY, REQUIRE_LV and RUNTIME; the control reports `0x22012201`.
This demonstrates a different effective loader policy, but does not prove that
WindowServer's complete environment is compatible.

Read-only API and flag definitions:
[XNU codesign.h](https://github.com/apple-oss-distributions/xnu/blob/xnu-11417.140.69/bsd/sys/codesign.h),
[cs_blobs.h](https://github.com/apple-oss-distributions/xnu/blob/xnu-11417.140.69/osfmk/kern/cs_blobs.h).
