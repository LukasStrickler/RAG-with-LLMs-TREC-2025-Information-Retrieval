import os

from sshtunnel import SSHTunnelForwarder


class SSHTunnelManager:
    """
    Manages SSH tunnels for accessing remote services (Solr, Qdrant, Postgres).
    """

    def __init__(self):
        self.ssh_host = os.getenv("SSH_HOST")
        self.ssh_user = os.getenv("SSH_USER")
        self.ssh_key_path = os.getenv("SSH_KEY_PATH")
        self.ssh_password = os.getenv("SSH_PASSWORD")

        # Remote hosts (default to localhost if not specified, but user requested internal IPs)
        self.remote_solr_host = os.getenv("REMOTE_SOLR_HOST", "localhost")
        self.remote_qdrant_host = os.getenv("REMOTE_QDRANT_HOST", "localhost")
        self.remote_db_host = os.getenv("REMOTE_DB_HOST", "localhost")

        # Remote ports
        self.remote_solr_port = int(os.getenv("REMOTE_SOLR_PORT", "8983"))
        self.remote_qdrant_port = int(os.getenv("REMOTE_QDRANT_PORT", "6333"))
        self.remote_db_port = int(os.getenv("REMOTE_DB_PORT", "5432"))

        self.server: SSHTunnelForwarder | None = None
        self.local_ports: dict[str, int] = {}

    def start(self) -> dict[str, int]:
        """
        Starts the SSH tunnel and returns the local ports mapped to the remote services.
        """
        if not self.ssh_host or not self.ssh_user:
            raise ValueError("SSH_HOST and SSH_USER environment variables must be set.")

        ssh_args = {
            "ssh_address_or_host": (self.ssh_host, 22),
            "ssh_username": self.ssh_user,
            "remote_bind_addresses": [
                (self.remote_solr_host, self.remote_solr_port),
                (self.remote_qdrant_host, self.remote_qdrant_port),
                (self.remote_db_host, self.remote_db_port),
            ],
        }

        if self.ssh_key_path:
            ssh_args["ssh_pkey"] = self.ssh_key_path
        elif self.ssh_password:
            ssh_args["ssh_password"] = self.ssh_password
        else:
            # Assume agent auth or no auth needed? Better to warn.
            print(
                "Warning: No SSH key or password provided. Attempting to use SSH agent or default keys."
            )

        self.server = SSHTunnelForwarder(**ssh_args)
        self.server.start()

        # sshtunnel assigns random local ports if we don't specify them.
        # We need to retrieve them.
        # The order in tunnel_bindings matches remote_bind_addresses.

        self.local_ports["solr"] = self.server.tunnel_bindings[
            (self.remote_solr_host, self.remote_solr_port)
        ][1]
        self.local_ports["qdrant"] = self.server.tunnel_bindings[
            (self.remote_qdrant_host, self.remote_qdrant_port)
        ][1]
        self.local_ports["db"] = self.server.tunnel_bindings[
            (self.remote_db_host, self.remote_db_port)
        ][1]

        print(f"SSH Tunnel started. Local ports: {self.local_ports}")
        return self.local_ports

    def stop(self):
        """Stops the SSH tunnel."""
        if self.server:
            self.server.stop()
            self.server = None
            print("SSH Tunnel stopped.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
