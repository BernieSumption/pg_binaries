# Windows archive verification

`python -m verification.windows.release` runs the shared release checks for Windows x86_64 archives. Windows on ARM can execute these archives through x64 translation. The verifier requires Visual Studio `dumpbin` for PE inspection; PostgreSQL runs with an environment whose `PATH` contains only its extracted `bin` directory. Windows process support variables are retained, and disposable servers listen on an ephemeral loopback TCP port.

The PostgreSQL-only combination checks the selected capabilities, source-derived built-in extension inventory, SQL operations, dump and restore, and mutual TLS authentication. Windows excludes `uuid-ossp`, as specified in the PostgreSQL build options.

The TLS probe reads PostgreSQL's public test certificates and keys from the same checksum-verified source archive used for built-in inventory. The server and client certificate files include their intermediate certificates. The client identity is `ssltestuser`; the probe creates that database user and checks that `sslinfo` reports its authenticated certificate identity. These upstream test certificates expire in 2050. No OpenSSL executable or builder DLL search path is required to prepare these fixtures on Windows.

Dependency isolation checks the backend and SQL module import closures. Two extension packages conflict when they supply different bytes under the same case-insensitive DLL basename. Distinct DLL names bind independently, so shared function export names do not create a conflict. Every loaded packaged file must have archive ownership. The separate PE check rejects missing non-system imports and incompatible architecture.
