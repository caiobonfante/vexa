---
title: 'How to Set Up Self-Hosted Meeting Transcription in 5 Minutes'
date: '2025-12-02'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/self-hosted-meeting-transcription-setup.png'
slug: 'how-to-set-up-self-hosted-meeting-transcription-5-minutes'
summary: "Step-by-step guide to deploy self-hosted meeting transcription with Vexa. Deploy in 5 minutes with Docker. Free tier available. Open source."
---

Looking for a **self-hosted meeting transcription** solution that gives you complete control over your data? With the open-source **[Vexa API](https://github.com/Vexa-ai/vexa)**, you can deploy your own meeting transcription infrastructure in about one hour using Docker—no cloud dependencies, no data leaving your infrastructure, and full compliance with GDPR and data sovereignty requirements.

**Self-hosted meeting transcription** is the ideal solution for organizations that need to keep sensitive meeting data on-premises, comply with strict privacy regulations, or simply want full control over their transcription infrastructure. Unlike cloud-based solutions, self-hosted transcription ensures your data never leaves your network, giving you complete privacy and security.

---

## Why Choose Self-Hosted Meeting Transcription?

Before we dive into the setup, let's understand why **self-hosted meeting transcription** might be the right choice for you:

- **Complete Data Control** – Your meeting transcripts never leave your infrastructure
- **GDPR & Compliance** – Meet strict data sovereignty requirements
- **Cost Efficiency** – No per-minute pricing, scale on your own hardware
- **Customization** – Modify and extend the open-source code to fit your needs
- **Privacy-First** – Perfect for healthcare, legal, and enterprise use cases

---

## Prerequisites

Before you begin, make sure you have:

1. **Docker installed** – [Download Docker](https://www.docker.com/products/docker-desktop/)
2. **Basic command line knowledge** – Familiarity with terminal/command prompt
3. **System requirements:**
   - 4GB RAM minimum (8GB recommended)
   - 10GB free disk space
   - CPU: Any modern processor (GPU optional for better performance)

**Optional but recommended:**
- GPU support (NVIDIA) for faster, higher-quality transcription
- Docker Compose for easier management

---

## Step-by-Step Setup

### Step 1: Clone the Vexa Repository

Open your terminal and clone the Vexa repository:

```bash
git clone https://github.com/Vexa-ai/vexa.git
cd vexa
```

This will download the latest version of Vexa, including all necessary components for **self-hosted meeting transcription**.

---

### Step 2: Deploy with Docker

Vexa makes **self-hosted meeting transcription** deployment incredibly simple. Choose your deployment option:

#### Option A: CPU Deployment (Fastest Setup)

For development and testing, or if you don't have a GPU:

```bash
make all
```

This command will:
- Build all Docker containers (takes some time on first run)
- Use Whisper tiny model (fast, good for development)
- Run database migrations (if necessary)
- Start all services automatically
- Run a simple test to verify everything works

#### Option B: GPU Deployment (Production Quality)

For production deployments with better transcription quality:

```bash
make all TARGET=gpu
```

This uses the Whisper medium model for higher accuracy. **Note:** Requires NVIDIA GPU with CUDA support.

#### Option C: Fresh VM Setup (Automated)

If you're setting up on a fresh GPU VM in the cloud (tested on Vultr `vcg-a16-6c-64g-16vram`):

```bash
sudo ./fresh_setup.sh --gpu    # or --cpu for CPU-only hosts
make all TARGET=gpu             # or make all for CPU
```

This automated script sets up everything for you on a fresh VM, including Docker, NVIDIA drivers, and all prerequisites.

**Reference:** [Deployment Guide](https://github.com/Vexa-ai/vexa/blob/main/docs/deployment.mdx)

---

### Step 3: Verify Installation

Once the containers are running, verify your **self-hosted meeting transcription** setup is working:

```bash
# Check container status
make ps

# View logs
make logs

# Quick API connectivity test
make test-api
```

**Services are available at:**
- **API Gateway:** http://localhost:18056/docs (API documentation)
- **Admin API:** http://localhost:18057/docs (Admin endpoints)

**Reference:** [Deployment Guide](https://github.com/Vexa-ai/vexa/blob/main/docs/deployment.mdx)

---

### Step 4: Create User and Get API Key

For **self-hosted meeting transcription** deployments, you need to create users and API tokens through the admin API.

#### Create a User

```bash
curl -X POST http://localhost:18056/admin/users \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: token" \
  -d '{
    "email": "user@example.com",
    "name": "John Doe",
    "max_concurrent_bots": 2
  }'
```

**Note:** The default admin token is `token` (check your `.env` file for `ADMIN_API_TOKEN`).

#### Generate API Token

```bash
# Replace USER_ID with the user's ID from step above
curl -X POST http://localhost:18056/admin/users/1/tokens \
  -H "X-Admin-API-Key: token"
```

**⚠️ Important:** Save the token immediately - it cannot be retrieved later!

**For hosted deployments**, you can get API keys from the [Vexa dashboard](https://vexa.ai/dashboard/api-keys).

**Reference:** [Self-Hosted Management Guide](https://github.com/Vexa-ai/vexa/blob/main/docs/self-hosted-management.mdx)

---

### Step 5: Test Your Self-Hosted Transcription

Test your **self-hosted meeting transcription** setup with a live meeting:

```bash
# Use the built-in test command (easiest way)
make test MEETING_ID=abc-defg-hij  # Use your Google Meet ID (xxx-xxxx-xxx format)
```

**What to expect:**
1. Bot joins your Google Meet
2. Admit the bot when prompted
3. Start speaking to see real-time transcripts

**Or test with API directly:**

```bash
# Start a transcription bot for a Google Meet
curl -X POST http://localhost:18056/bots \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -d '{
    "platform": "google_meet",
    "native_meeting_id": "your-meeting-id-xxx-xxxx-xxx"
  }'
```

If successful, you'll receive a bot ID and the bot will join your meeting to start transcribing.

---

## Management Commands

For managing your **self-hosted meeting transcription** deployment:

```bash
make ps        # Show container status
make logs      # View logs from all services
make down      # Stop all services
make test-api  # Quick API connectivity test
```

**Reference:** [Deployment Guide](https://github.com/Vexa-ai/vexa/blob/main/docs/deployment.mdx)

---

## User and Token Management

For production **self-hosted meeting transcription** deployments, you'll need to manage users and API tokens:

### Complete Workflow Example

```bash
# Step 1: Create user
USER_RESPONSE=$(curl -s -X POST http://localhost:18056/admin/users \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: token" \
  -d '{
    "email": "newuser@example.com",
    "name": "New User",
    "max_concurrent_bots": 2
  }')

USER_ID=$(echo $USER_RESPONSE | jq -r '.id')
echo "Created user with ID: $USER_ID"

# Step 2: Generate API token
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:18056/admin/users/${USER_ID}/tokens \
  -H "X-Admin-API-Key: token")

API_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.token')
echo "Generated token: $API_TOKEN"

# Step 3: Test user API access
curl -X GET "http://localhost:18056/meetings" \
  -H "X-API-Key: $API_TOKEN"
```

**For detailed user and token management**, see the [Self-Hosted Management Guide](https://github.com/Vexa-ai/vexa/blob/main/docs/self-hosted-management.mdx).

This guide covers:
- Creating and managing users
- Generating and revoking API tokens
- Updating user settings (bot limits, etc.)
- Complete workflow examples with curl and Python

---

## Troubleshooting

### Common Issues and Solutions

**Issue: Containers won't start**
- **Solution:** Check Docker is running: `docker ps`
- Verify you have enough resources: `docker stats`

**Issue: Transcription quality is poor**
- **Solution:** Use GPU deployment: `make all TARGET=gpu`
- Or switch to a larger Whisper model in configuration

**Issue: API calls failing**
- **Solution:** Verify API key is correct
- Check API service is running: `make ps` or `docker logs`
- Test API connectivity: `make test-api`
- Ensure firewall allows connections on port 18056 (API) and 18057 (Admin API)
- Verify you're using the correct port: `http://localhost:18056` (not 8080)

**Issue: Bot not joining meetings**
- **Solution:** Verify meeting ID format is correct (Google Meet: `xxx-xxxx-xxx`)
- Check bot service logs: `make logs` or `docker logs`
- Ensure network connectivity to meeting platform
- Admit the bot when it tries to join the meeting
- Use `make test MEETING_ID=xxx-xxxx-xxx` for easier testing

### Performance Optimization

For better **self-hosted meeting transcription** performance:

1. **Use GPU acceleration** – Significantly faster transcription
2. **Increase resources** – Allocate more RAM/CPU to containers
3. **Optimize Whisper model** – Balance speed vs. quality for your use case
4. **Scale horizontally** – Run multiple transcription workers for high volume

---

## Next Steps

Now that you have **self-hosted meeting transcription** running, here's what to do next:

### Integration Guides

- **[Integrate with Google Meet](https://vexa.ai/blog/google-meet-transcription-n8n-workflow)** – Complete Google Meet integration guide
- **[Microsoft Teams Integration](https://vexa.ai/blog/vexa-v0-6-microsoft-teams-support)** – Set up Teams transcription
- **[n8n Workflow Automation](https://vexa.ai/blog/google-meet-transcription-n8n-workflow)** – Automate transcriptions with n8n

### API Documentation

- **[Deployment Guide](https://github.com/Vexa-ai/vexa/blob/main/docs/deployment.mdx)** – Complete deployment instructions
- **[Self-Hosted Management Guide](https://github.com/Vexa-ai/vexa/blob/main/docs/self-hosted-management.mdx)** – User and token management
- **[API Reference](http://localhost:18056/docs)** – Interactive API documentation (when running locally)
- **[WebSocket Streaming](https://github.com/Vexa-ai/vexa/blob/main/docs/websocket.mdx)** – Real-time transcript streaming
- **[MCP Server Setup](https://vexa.ai/blog/claude-desktop-vexa-mcp-google-meet-transcripts)** – Integrate with AI agents

### Additional Resources

- **[Get Started Guide](https://vexa.ai/get-started)** – More detailed setup instructions
- **[Pricing](https://vexa.ai/pricing)** – Compare self-hosted vs. hosted options
- **[GitHub Repository](https://github.com/Vexa-ai/vexa)** – Star the project, contribute, or report issues
- **[Video Tutorial](https://www.youtube.com/watch?v=bHMIByieVek)** – 3-minute setup guide

---

## Why Vexa for Self-Hosted Meeting Transcription?

Vexa is the leading open-source solution for **self-hosted meeting transcription** because:

- ✅ **Apache-2.0 Licensed** – Truly open source, no vendor lock-in
- ✅ **Production-Ready** – Used by enterprises and developers worldwide
- ✅ **Active Community** – Regular updates, contributions, and support
- ✅ **Multiple Platforms** – Google Meet, Microsoft Teams, and more
- ✅ **Real-Time & Post-Meeting** – WebSocket streaming and full transcripts
- ✅ **Developer-Friendly** – REST API, WebSocket, MCP server support

---

## Join the Community

Get support, share your **self-hosted meeting transcription** setups, and contribute:

- **[Discord Community](https://discord.gg/Ga9duGkVz9)** – Real-time support and discussions
- **[GitHub Issues](https://github.com/Vexa-ai/vexa/issues)** – Report bugs or request features
- **[Star on GitHub](https://github.com/Vexa-ai/vexa)** – Show your support for open-source transcription

---

## Conclusion

Setting up **self-hosted meeting transcription** with Vexa takes about one hour and gives you complete control over your meeting data. Whether you need GDPR compliance, data sovereignty, or simply want to avoid cloud dependencies, Vexa's open-source solution provides enterprise-grade transcription that runs entirely on your infrastructure.

**Ready to get started?**
1. [Clone the repository](https://github.com/Vexa-ai/vexa)
2. Run `make all`
3. Start transcribing meetings in minutes

For questions or support, join our [Discord community](https://discord.gg/Ga9duGkVz9) or check out our [deployment documentation](https://github.com/Vexa-ai/vexa/blob/main/docs/deployment.mdx).

---

**Related Articles:**
- [Privacy-First Meeting Transcription: Why Self-Hosted Matters](https://vexa.ai/blog/privacy-first-meeting-transcription-why-self-hosted-matters)
- [Open Source Transcription API: Complete Guide](https://vexa.ai/blog/open-source-transcription-api-complete-guide)

