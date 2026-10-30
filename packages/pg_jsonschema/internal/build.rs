fn main() {
    println!("cargo::rerun-if-env-changed=PG_LDFLAGS");
    // Cargo link instructions preserve upstream Rust flags and caller overrides.
    for flag in std::env::var("PG_LDFLAGS").unwrap_or_default().split_whitespace() {
        println!("cargo::rustc-link-arg-cdylib={flag}");
    }
}
