# Letta Self-Hosted API Guide

## Quick Reference for Remote API Access

This guide documents how to connect to our self-hosted Letta server through a Pinggy tunnel, since official documentation now only covers the cloud service.

---

## Connection Details

**Base URL**: `https://cyansociety.a.pinggy.link`

**Authentication**: Password-based (not API key)
- Password: `TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz`

---

## Authentication Methods

Both methods work interchangeably:

### Method 1: Bearer Token (Recommended)
```bash
-H "Authorization: Bearer TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
```

### Method 2: X-BARE-PASSWORD Header
```bash
-H "X-BARE-PASSWORD: TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
```

---

## API Endpoints

**Important**: The base API path is `/v1/`, NOT `/api/v1/`

### Core Endpoints

**Health Check**
```bash
curl -X GET "https://cyansociety.a.pinggy.link/v1/health/" \
  -H "Authorization: Bearer TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
```

**List All Agents**
```bash
curl -X GET "https://cyansociety.a.pinggy.link/v1/agents/" \
  -H "Authorization: Bearer TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
```

**Get Specific Agent**
```bash
curl -X GET "https://cyansociety.a.pinggy.link/v1/agents/{agent-id}" \
  -H "Authorization: Bearer TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
```

**List Agent Messages**
```bash
curl -X GET "https://cyansociety.a.pinggy.link/v1/agents/{agent-id}/messages" \
  -H "Authorization: Bearer TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
```

---

## Infrastructure Details

### Server Setup
- **Hosting**: Hetzner VPS
- **Internal Address**: `localhost:8283` (HTTP)
- **External Access**: Pinggy tunnel provides HTTPS termination
- **Docker Network**: Host network mode

### Pinggy Tunnel (systemd)
```bash
# Service location
/etc/systemd/system/pinggy-tunnel.service

# Tunnel command
ssh -p 443 -R0:localhost:8283 -o StrictHostKeyChecking=no \
  -o ServerAliveInterval=30 6fdhwW1IdVi@pro.pinggy.io
```

**Manage the tunnel:**
```bash
# Check status
sudo systemctl status pinggy-tunnel

# Restart if needed
sudo systemctl restart pinggy-tunnel

# View logs
sudo journalctl -u pinggy-tunnel -f
```

---

## Troubleshooting

### Common Issues

**"Not Found" or 404 Errors**
- Make sure you're using `/v1/` not `/api/v1/`
- Include the trailing slash: `/v1/health/` not `/v1/health`

**"Unauthorized" or 401 Errors**
- Verify password matches: `TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz`
- Check Authorization header format: `Bearer <password>`
- Alternative: Try X-BARE-PASSWORD header

**Connection Timeouts**
- Check if pinggy-tunnel service is running
- Verify Letta container is healthy: `docker ps`
- Check Docker logs: `docker logs <letta-container-id>`

### Direct Server Test

If remote API calls fail, test directly on the server:

```bash
# SSH to your VPS
ssh root@157.180.34.8

# Test local endpoint
sudo docker exec $(docker ps -q --filter name=letta) \
  curl -s -H "Authorization: Bearer TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz" \
  http://localhost:8283/v1/health/
```

---

## Environment Variables

When using Letta client libraries, set:

```bash
export LETTA_BASE_URL="https://cyansociety.a.pinggy.link"
export LETTA_API_KEY="TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
```

---

## Notes

- This setup uses password authentication, not token-based auth
- The tunnel uses no path rewriting (direct port forwarding)
- API_PREFIX in runtime is `/v1/` (confirmed from server code)
- All API endpoints are versioned under `/v1/`

---

## Support

For issues specific to this self-hosted setup, check:
- Docker container logs
- Pinggy tunnel status
- Letta server version: `v0.13.0` (check health endpoint)
