use zed_extension_api::{self as zed, Command, ContextServerId, Project, Result};

/// Registers the `dsa mcp` server as a context server, so Zed's agent gets the DSA practice tools.
struct DsaPractice;

impl zed::Extension for DsaPractice {
    fn new() -> Self {
        DsaPractice
    }

    fn context_server_command(&mut self, _id: &ContextServerId, _project: &Project) -> Result<Command> {
        // Login shell so ~/.local/bin (where install.sh puts `dsa`) is on PATH even when Zed is launched from the desktop.
        Ok(Command {
            command: "/bin/sh".into(),
            args: vec!["-lc".into(), "exec dsa mcp".into()],
            env: vec![],
        })
    }
}

zed::register_extension!(DsaPractice);
