import QtQuick
import Quickshell.Io

Item {
    id: root
    signal finished(string color, bool failed)

    Process {
        // Hyprpicker writes the selected color and its diagnostics to stdout.
        command: ["bash", "-c", "exec hyprpicker --format=hex --no-fancy --render-inactive"]
        running: true
        stdout: StdioCollector { id: sample; waitForEnd: true }
        stderr: StdioCollector { id: errors; waitForEnd: true }
        onExited: function(code) {
            const output = sample.text
            const color = output.split("\n").map(line => line.trim()).find(line => /^#[0-9a-fA-F]{6}$/.test(line))
            root.finished(code === 0 ? color || "" : "",
                code !== 0 || /^\[(?:ERR|CRITICAL)\]/m.test(output) || errors.text.trim() !== "")
        }
    }
}
