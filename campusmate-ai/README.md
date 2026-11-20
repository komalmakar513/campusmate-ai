# 🎓 CampusMate AI
Smart college helpdesk on Azure. Students submit feedback (AI sentiment + key phrases),
read notice images (OCR), and translate English ⇄ Hindi. Admin sees a live dashboard.

## Run locally (Demo Mode, no Azure needed)
    pip install -r requirements.txt
    python app.py        # http://127.0.0.1:5000

## Deploy to Azure
    az login
    bash deploy.sh campusmate-tannu123     # name must be globally unique
    # CLEAN UP after demo to avoid charges:
    az group delete -n rg-campusmate --yes

## AZ-900 concepts used
| Concept | Where |
|---|---|
| Resource Group + Tags | rg-campusmate, tagged |
| PaaS (App Service) | web hosting, no VM management |
| Regions | centralindia (low latency + data residency) |
| Shared responsibility | Azure runs OS/runtime, we own code + keys |
| Cost Management / Pricing calc | B1 plan; delete RG after demo |
| Monitoring | /health + App Service Metrics / Log stream |
| Security | keys in App Settings, never in code |

## AI-900 concepts used
| Workload | Feature |
|---|---|
| NLP | Sentiment analysis, key phrase extraction (Azure AI Language) |
| Computer Vision | OCR / Read (Azure AI Vision) |
| NLP | Translator (Azure AI Translator) |
| Responsible AI | Transparency (shows sentiment + phrases), privacy (no personal data stored) |
