"""Test Docker connection for debugging."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import docker
import sys
from app.core.config import settings

print("Testing Docker connection...")
print("=" * 50)

# Check environment variables
import os
docker_host = os.environ.get('DOCKER_HOST')
print(f"DOCKER_HOST env var: {docker_host if docker_host else '(not set)'}")

client = None

# Test each connection method individually
print("\n1. Testing docker.from_env()...")
try:
    client1 = docker.from_env()
    version = client1.version()
    print(f"   [OK] Success! Docker version: {version.get('Version', 'unknown')}")
    client = client1
except Exception as e:
    print(f"   [FAILED] {type(e).__name__}: {e}")

if not client:
    print("\n2. Testing configured DOCKER_SOCKET_URL...")
    print(f"   URL: {settings.DOCKER_SOCKET_URL}")
    try:
        client2 = docker.DockerClient(base_url=settings.DOCKER_SOCKET_URL)
        version = client2.version()
        print(f"   [OK] Success! Docker version: {version.get('Version', 'unknown')}")
        client = client2
    except Exception as e:
        print(f"   [FAILED] {type(e).__name__}: {e}")

if not client and sys.platform == "win32":
    print("\n3. Testing Windows named pipe (direct)...")
    npipe = "npipe:////./pipe/docker_engine"
    print(f"   URL: {npipe}")
    try:
        # Try using APIClient first (lower level)
        api_client = docker.APIClient(base_url=npipe)
        version_info = api_client.version()
        print(f"   [OK] APIClient Success! Docker version: {version_info.get('Version', 'unknown')}")
        # Now try DockerClient
        client3 = docker.DockerClient(base_url=npipe)
        version = client3.version()
        print(f"   [OK] DockerClient Success! Docker version: {version.get('Version', 'unknown')}")
        client = client3
    except Exception as e:
        print(f"   [FAILED] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

# Test the connection function directly
print("\n4. Testing _make_docker_client() function...")
from app.services.docker_runner import docker_runner, _make_docker_client
client = _make_docker_client()

if client:
    print("[OK] Docker client created successfully!")
    try:
        # Test connection
        version = client.version()
        print(f"[OK] Docker version: {version.get('Version', 'unknown')}")
        print(f"[OK] Docker API version: {version.get('ApiVersion', 'unknown')}")
        
        # Test listing containers
        containers = client.containers.list(limit=1)
        print(f"[OK] Can list containers (found {len(containers)} container(s))")
        
        # Test docker_runner instance
        if docker_runner.client:
            print("[OK] DockerRunner instance has active client")
        else:
            print("[ERROR] DockerRunner instance has no client")
            
    except Exception as e:
        print(f"[ERROR] Error testing Docker connection: {e}")
        import traceback
        traceback.print_exc()
else:
    print("[ERROR] Failed to create Docker client")
    print("\nTroubleshooting:")
    print("1. Make sure Docker Desktop is running")
    print("2. Check if Docker Desktop exposes the daemon on: npipe:////./pipe/docker_engine")
    print("3. Try running: docker ps (in terminal) to verify Docker CLI works")

print("=" * 50)
