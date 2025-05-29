#!/usr/bin/env python3
"""
NATS Multi-Agent System Orchestrator
Manages all services with centralized environment loading and graceful shutdown.
"""

import asyncio
import subprocess
import signal
import sys
import os
import time
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

class ServiceManager:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_path = project_root / "src"
        self.processes: Dict[str, subprocess.Popen] = {}
        self.nats_process: Optional[subprocess.Popen] = None
        self.logger = logging.getLogger("ServiceManager")

        # Load environment variables once for all services
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            self.logger.info(f"Loaded environment from {env_file}")
        else:
            self.logger.warning(f"No .env file found at {env_file}")

        # Service definitions with dependencies
        self.services = {
            "captain": {
                "script": "latest_ai_development/tools/captain/captain_agent.py",
                "description": "Captain Agent - Main orchestrator",
                "dependencies": ["nats"],
                "startup_delay": 1
            },
            "prompt_processor": {
                "script": "latest_ai_development/tools/captain/prompt_processor_subagent.py",
                "description": "Prompt Processor - Converts prompts to structured data",
                "dependencies": ["nats"],
                "startup_delay": 1
            },
            "executor": {
                "script": "latest_ai_development/tools/agent_registry/executor_subagent.py",
                "description": "Executor - Distributes tasks to sub-agents",
                "dependencies": ["nats"],
                "startup_delay": 2
            },
            "stock_news": {
                "script": "latest_ai_development/tools/sub_agents/stock_news_agent.py",
                "description": "Stock News Agent",
                "dependencies": ["nats", "executor"],
                "startup_delay": 3
            },
            "stock_price": {
                "script": "latest_ai_development/tools/sub_agents/stock_price_agent.py",
                "description": "Stock Price Agent",
                "dependencies": ["nats", "executor"],
                "startup_delay": 3
            },
            "price_predictor": {
                "script": "latest_ai_development/tools/sub_agents/price_predictor_agent.py",
                "description": "Price Predictor Agent",
                "dependencies": ["nats", "executor"],
                "startup_delay": 3
            }
        }

    def check_nats_server(self) -> bool:
        """Check if NATS server is available."""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', 4222))
            sock.close()
            return result == 0
        except Exception:
            return False

    def start_nats_server(self) -> bool:
        """Start NATS server if not running."""
        if self.check_nats_server():
            self.logger.info("NATS server already running")
            return True

        self.logger.info("Starting NATS server...")
        try:
            # Check if nats-server binary exists in project root
            nats_binary = self.project_root / "nats-server"
            if nats_binary.exists():
                cmd = [str(nats_binary), "-DV"]
            else:
                cmd = ["nats-server", "-DV"]

            self.nats_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.project_root
            )

            # Wait for NATS to start
            for _ in range(10):
                time.sleep(0.5)
                if self.check_nats_server():
                    self.logger.info("NATS server started successfully")
                    return True

            self.logger.error("NATS server failed to start within timeout")
            return False

        except FileNotFoundError:
            self.logger.error("NATS server binary not found. Install from https://nats.io/download/")
            return False
        except Exception as e:
            self.logger.error(f"Failed to start NATS server: {e}")
            return False

    def start_service(self, service_name: str) -> bool:
        """Start a single service."""
        if service_name in self.processes:
            self.logger.warning(f"Service {service_name} already running")
            return True

        service_config = self.services[service_name]
        script_path = self.src_path / service_config["script"]

        if not script_path.exists():
            self.logger.error(f"Script not found: {script_path}")
            return False

        self.logger.info(f"Starting {service_config['description']}...")

        try:
            # Set up environment for the subprocess
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.src_path)

            # For live logs, set stdout=None, stderr=None
            # For captured logs, keep as is
            show_logs = os.environ.get("SHOW_SERVICE_LOGS", "true").lower() == "true"

            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=self.project_root,
                env=env,
                stdout=None if show_logs else subprocess.PIPE,
                stderr=None if show_logs else subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            self.processes[service_name] = process
            self.logger.info(f"✓ {service_name} started (PID: {process.pid})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start {service_name}: {e}")
            return False

    def stop_service(self, service_name: str) -> None:
        """Stop a single service gracefully."""
        if service_name not in self.processes:
            return

        process = self.processes[service_name]
        self.logger.info(f"Stopping {service_name}...")

        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Force killing {service_name}")
                process.kill()
                process.wait()
        except Exception as e:
            self.logger.error(f"Error stopping {service_name}: {e}")
        finally:
            del self.processes[service_name]

    def stop_all_services(self) -> None:
        """Stop all services in reverse dependency order."""
        self.logger.info("Stopping all services...")

        # Stop services in reverse order
        service_names = list(self.services.keys())
        for service_name in reversed(service_names):
            self.stop_service(service_name)

        # Stop NATS server
        if self.nats_process:
            self.logger.info("Stopping NATS server...")
            try:
                self.nats_process.terminate()
                self.nats_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.nats_process.kill()
                self.nats_process.wait()
            self.nats_process = None

    def start_all_services(self) -> bool:
        """Start all services with proper dependency ordering."""
        self.logger.info("Starting NATS Multi-Agent System...")

        # Start NATS server first
        if not self.start_nats_server():
            return False

        # Start services with delays for dependency management
        for service_name, config in self.services.items():
            if not self.start_service(service_name):
                self.logger.error(f"Failed to start {service_name}")
                return False

            # Wait for service to initialize
            time.sleep(config.get("startup_delay", 1))

        self.logger.info("🚀 All services started successfully!")
        return True

    def monitor_services(self) -> None:
        """Monitor service health and restart if needed."""
        while True:
            try:
                time.sleep(5)  # Check every 5 seconds

                for service_name, process in list(self.processes.items()):
                    if process.poll() is not None:  # Process has terminated
                        self.logger.warning(f"Service {service_name} died, restarting...")
                        del self.processes[service_name]
                        self.start_service(service_name)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")

    def run_interactive_mode(self) -> None:
        """Run in interactive mode with command interface."""
        print("\n🤖 NATS Multi-Agent System Orchestrator")
        print("Commands: start, stop, restart, status, logs <service>, client, quit")

        while True:
            try:
                cmd = input("\n> ").strip().lower()

                if cmd == "start":
                    self.start_all_services()
                elif cmd == "stop":
                    self.stop_all_services()
                elif cmd == "restart":
                    self.stop_all_services()
                    time.sleep(2)
                    self.start_all_services()
                elif cmd == "status":
                    self.show_status()
                elif cmd.startswith("logs "):
                    service = cmd.split(" ", 1)[1]
                    self.show_logs(service)
                elif cmd == "client":
                    self.run_test_client()
                elif cmd in ["quit", "exit", "q"]:
                    break
                else:
                    print("Unknown command. Try: start, stop, restart, status, logs <service>, client, quit")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

        self.stop_all_services()

    def show_status(self) -> None:
        """Show status of all services."""
        print("\n📊 Service Status:")
        print("-" * 50)

        # NATS status
        nats_status = "🟢 Running" if self.check_nats_server() else "🔴 Stopped"
        print(f"NATS Server: {nats_status}")

        # Service status
        for service_name, config in self.services.items():
            if service_name in self.processes:
                process = self.processes[service_name]
                if process.poll() is None:
                    status = f"🟢 Running (PID: {process.pid})"
                else:
                    status = "🔴 Dead"
            else:
                status = "⚪ Stopped"

            print(f"{config['description']}: {status}")

    def show_logs(self, service_name: str) -> None:
        """Show recent logs for a service."""
        if service_name not in self.processes:
            print(f"Service {service_name} not running")
            return

        process = self.processes[service_name]
        if process.stdout:
            print(f"\n📝 Recent logs for {service_name}:")
            print("-" * 40)
            # This is a simplified log display - in production you'd want proper log aggregation
            print("(Live monitoring not implemented - check service output directly)")

    def run_test_client(self) -> None:
        """Run the test client."""
        client_script = self.src_path / "client.py"
        if not client_script.exists():
            print("Client script not found")
            return

        print("🧪 Running test client...")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.src_path)

            subprocess.run(
                [sys.executable, str(client_script)],
                cwd=self.project_root,
                env=env
            )
        except Exception as e:
            print(f"Failed to run client: {e}")


def main():
    # Find project root (directory containing this script)
    script_path = Path(__file__).resolve()
    project_root = script_path.parent

    # Create service manager
    manager = ServiceManager(project_root)

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\n🛑 Received shutdown signal...")
        manager.stop_all_services()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "start":
            if manager.start_all_services():
                print("\n✅ System started. Press Ctrl+C to stop.")
                try:
                    manager.monitor_services()
                except KeyboardInterrupt:
                    pass
            manager.stop_all_services()

        elif command == "stop":
            manager.stop_all_services()

        elif command == "status":
            manager.show_status()

        elif command == "interactive":
            manager.run_interactive_mode()

        else:
            print("Usage: python orchestrator.py [start|stop|status|interactive]")
            print("  start       - Start all services and monitor")
            print("  stop        - Stop all services")
            print("  status      - Show service status")
            print("  interactive - Interactive mode with command interface")
    else:
        # Default to interactive mode
        manager.run_interactive_mode()


if __name__ == "__main__":
    main()