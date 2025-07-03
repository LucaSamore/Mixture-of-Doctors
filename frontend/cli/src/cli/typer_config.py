import click


def set_usage_command(custom_command: str) -> None:
    """Patch Click formatter to customize command usage display in help text"""

    def custom_write_usage(self, prog, args="", prefix=None):
        if prefix is None:
            prefix = "Usage: "
        self.write(f"{prefix}{custom_command}")

    click.formatting.HelpFormatter.write_usage = custom_write_usage
