# JAIMES AI Executive - Deployment Guide

## 🚀 Complete Deployment Solutions

This guide covers all deployment options for JAIMES AI Executive, from local testing to production cloud deployment and mini-PC installations.

## 📋 Quick Start

### Prerequisites
- Python 3.11+
- Docker (for containerized deployments)
- Git (for version control)
- Your API keys ready

### Environment Variables Required
```bash
# Core API Keys
GROQ_API_KEY=your_groq_api_key_here

# Optional API Keys (for full functionality)
VEHICLE_DATABASE_API_KEY=your_vehicle_db_key
PLATETOVIN_API_KEY=your_platetovin_key
SHOPWARE_API_KEY=your_shopware_key

# Configuration
GROQ_MODEL=llama3-8b-8192
DEPLOY_ENV=prod
LOG_LEVEL=INFO
```

## 🎯 Deployment Options

### 1. Local Testing (No APIs Required)
Perfect for initial testing and demos:

```bash
# Clone and setup
git clone your-repo-url
cd jaimes-ai-executive
cp .env.example .env

# Run in testing mode
python main.py --mode testing --demo
```

**Features in Testing Mode:**
- ✅ Full conversation flows with mock data
- ✅ Simulated API responses (no costs)
- ✅ Complete customer experience demo
- ✅ Perfect for Rob's initial testing

### 2. Render.com Cloud Deployment
Best for production cloud hosting:

#### Step 1: Prepare Repository
```bash
# Ensure you have these files:
- render.yaml
- requirements-render.txt
- main.py
- All core system files
```

#### Step 2: Deploy to Render
1. Push code to GitHub
2. Connect GitHub repo to Render
3. Render will automatically detect `render.yaml`
4. Set environment variables in Render dashboard:
   - `GROQ_API_KEY` (required)
   - `VEHICLE_DATABASE_API_KEY` (optional)
   - `PLATETOVIN_API_KEY` (optional)
   - `SHOPWARE_API_KEY` (optional)
5. Deploy!

#### Step 3: Verify Deployment
```bash
curl https://your-app.onrender.com/health
```

### 3. Docker Local Deployment
For local development with full containerization:

```bash
# Using Docker Compose (Recommended)
docker-compose up -d

# Or using Docker directly
docker build -t jaimes-ai-executive .
docker run -d -p 8000:8000 --env-file .env jaimes-ai-executive
```

### 4. Mini-PC Deployment
For on-premises installations at MileX locations:

```bash
# Use the deployment script
./deploy.sh minipc
```

This creates a `minipc-deployment/` package with:
- Complete JAIMES system
- Docker configuration
- Setup instructions
- Management scripts

## 🔧 Deployment Scripts

### Using the Deploy Script
```bash
# Make executable
chmod +x deploy.sh

# Available commands
./deploy.sh local      # Local Docker deployment
./deploy.sh render     # Prepare for Render
./deploy.sh minipc     # Create mini-PC package
./deploy.sh test       # Run testing mode
./deploy.sh clean      # Clean Docker containers
./deploy.sh logs       # View logs
./deploy.sh health     # Health check
```

### Manual Startup
```bash
# Make executable
chmod +x start.sh

# Run with environment detection
./start.sh
```

## 📊 Deployment Comparison

| Method | Best For | Pros | Cons |
|--------|----------|------|------|
| **Testing Mode** | Initial demos, Rob's testing | No API costs, full experience | Mock data only |
| **Render.com** | Production cloud | Auto-scaling, managed | Monthly cost |
| **Docker Local** | Development | Full control, real APIs | Manual management |
| **Mini-PC** | On-premises | Data privacy, no cloud costs | Hardware management |

## 🔍 Troubleshooting

### Common Issues

#### 1. Render Deployment Errors

**Error: `sqlite3` not found**
- **Solution**: Use `requirements-render.txt` (sqlite3 removed)

**Error: `pyaudio` build failed**
- **Solution**: Use `requirements-render.txt` (audio libs optimized for cloud)

#### 2. Docker Issues

**Error: Port already in use**
```bash
docker stop jaimes
docker rm jaimes
./deploy.sh local
```

**Error: Permission denied**
```bash
chmod +x start.sh deploy.sh
```

#### 3. API Connection Issues

**Error: GROQ API key invalid**
- Check your `.env` file
- Verify key in Render dashboard
- Ensure no extra spaces/quotes

### Health Checks

```bash
# Local health check
curl http://localhost:8000/health

# Render health check
curl https://your-app.onrender.com/health

# Docker logs
docker logs jaimes

# Application logs
tail -f logs/jaimes.log
```

## 🔒 Security Best Practices

### Environment Variables
- Never commit API keys to Git
- Use `.env` files for local development
- Use Render dashboard for cloud secrets
- Rotate keys regularly

### Network Security
- Use HTTPS in production
- Restrict CORS origins for production
- Enable rate limiting
- Monitor API usage

### Data Privacy
- Customer data is not stored permanently
- Conversation logs can be disabled
- VIN data is cached temporarily only
- Comply with automotive data regulations

## 📈 Monitoring and Maintenance

### Health Monitoring
```bash
# Automated health checks
curl -f http://localhost:8000/health || echo "Service down"

# Log monitoring
tail -f logs/jaimes.log | grep ERROR
```

### Performance Monitoring
- Monitor API response times
- Track conversation completion rates
- Monitor memory and CPU usage
- Set up alerts for failures

### Updates and Maintenance
```bash
# Update Docker deployment
docker-compose pull
docker-compose up -d

# Update Render deployment
git push origin main  # Auto-deploys

# Update mini-PC
# Copy new files and restart containers
```

## 🎯 Production Checklist

### Before Going Live
- [ ] All API keys configured
- [ ] Health checks passing
- [ ] CORS configured for production
- [ ] Logging configured
- [ ] Monitoring set up
- [ ] Backup strategy in place
- [ ] Team trained on deployment

### Launch Day
- [ ] Deploy to production
- [ ] Verify all endpoints
- [ ] Test complete conversation flows
- [ ] Monitor logs for errors
- [ ] Have rollback plan ready

### Post-Launch
- [ ] Monitor performance metrics
- [ ] Collect user feedback
- [ ] Plan feature updates
- [ ] Regular security updates

## 🆘 Support and Escalation

### Getting Help
1. Check this documentation
2. Review application logs
3. Test in isolation (testing mode)
4. Contact development team

### Emergency Procedures
1. **Service Down**: Use health checks to diagnose
2. **API Limits**: Switch to testing mode temporarily
3. **Performance Issues**: Check resource usage
4. **Data Issues**: Review conversation logs

---

## 📞 Contact Information

For deployment support or questions:
- Development Team: [Your contact info]
- Emergency Support: [Emergency contact]
- Documentation: [Link to full docs]

---

*This deployment guide ensures JAIMES can be successfully deployed in any environment, from initial testing to full production deployment across multiple MileX locations.*

