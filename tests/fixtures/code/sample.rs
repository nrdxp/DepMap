//! Sample Rust module for testing symbol search.

/// Greet someone by name.
pub fn greet(name: &str) -> String {
    format!("Hello, {}!", name)
}

/// A sample struct with methods.
pub struct Greeter {
    pub name: String,
}

impl Greeter {
    /// Create a new greeter.
    pub fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
        }
    }

    /// Say hello.
    pub fn say_hello(&self) -> String {
        greet(&self.name)
    }
}

/// A constant value.
pub const SAMPLE_CONSTANT: u32 = 100;
