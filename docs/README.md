# SAIGE Med-Spa AI Executive

## 🚀 What This Package Contains

SAIGE is an intelligent AI executive system designed specifically for med-spa businesses. It handles customer conversations, service selection, intake questionnaires, and integrates with your CRM automation workflows.

## 📦 Core Components

### **Main System**
- `complete_saige.py` - Core SAIGE AI executive with med-spa conversation flow
- `medspa_service_catalog.py` - Service catalog with CRM tag integration
- `booking_adapter.py` - Appointment booking and scheduling integration

### **Supporting Modules**
- `customer_identification_system.py` - Customer lookup and identification engine
- `returning_customer_flow.py` - Returning customer conversation management
- `session_manager.py` - Session persistence and Redis integration
- `main.py` - FastAPI application entry point

## 🎯 Key Features

### **Med-Spa Service Management**
- **6 Core Services**: consultation, facial, botox, filler, laser, massage
- **CRM Tag Integration**: Automatic tag application based on service selection
- **Automation Phase Detection**: Triggers appropriate nurture campaigns
- **Tailored Intake Questions**: Service-specific questionnaires

### **Conversation Intelligence**
- **State Machine**: Guided conversation flow from greeting to booking
- **Customer Recognition**: Identifies returning vs. new customers
- **Service Matching**: Natural language service identification
- **Progressive Intake**: Step-by-step customer information collection

### **CRM Integration**
- **Automation Triggers**: Phase 1-4 automation workflows
- **Tag Management**: RFM segmentation, membership status, engagement tracking
- **Data Collection**: Structured intake data for your automation campaigns

## 🔧 Configuration

### **Required Environment Variables**
- `GROQ_API_KEY` - LLM integration
- `GROQ_MODEL` - Model selection (default: llama3-8b-8192)
- `UPSTASH_REDIS_REST_URL` - Redis connection
- `UPSTASH_REDIS_REST_TOKEN` - Redis authentication
- `VAPI_API_KEY` - Voice API integration

### **Deployment**
- **Render Ready**: Configured for Render deployment
- **Redis Fallback**: Graceful fallback to in-memory storage
- **Environment Detection**: Automatic DEV/PROD configuration

## 🎭 Conversation Flow

1. **Customer Verification** → Identify returning vs. new customers
2. **Service Selection** → Match customer needs to available services
3. **Intake Questions** → Progressive service-specific questionnaires
4. **Scheduling** → Find available slots and confirm appointments
5. **CRM Integration** → Apply tags and trigger automation phases

## 🚨 Important Notes

- **No Automotive Code**: All old JAIMES automotive functionality removed
- **Med-Spa Focused**: Built specifically for med-spa business processes
- **CRM Ready**: Integrates with your existing CRM tags and automations
- **Testing Mode**: Includes mock data for development and testing

## 🎯 Next Steps

1. **Deploy to Render** - All configuration issues resolved
2. **Connect Your CRM** - Map your tags to automation phases
3. **Customize Services** - Add your specific service offerings
4. **Test Conversations** - Verify med-spa conversation flows

---

*SAIGE: Your intelligent med-spa AI executive for seamless customer experiences and CRM automation!*

