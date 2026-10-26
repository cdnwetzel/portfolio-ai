# Billing & Stripe Integration

## Pricing Tiers

| Feature | Free | Pro | Enterprise |
|---------|------|-----|-----------|
| Monthly Cost | $0 | $29 | Custom |
| Monthly Tokens | 100k | 1M | Unlimited |
| Concurrent Requests | 5 | 50 | 500+ |
| Knowledge Bases | 1 | 10 | Unlimited |
| Storage | 100 MB | 10 GB | Unlimited |
| API Access | No | Yes | Yes |
| Support | Community | Email | Dedicated |
| SLA | None | 99.5% | 99.9% |

## Stripe Setup

### 1. Create Stripe Account

Visit [stripe.com](https://stripe.com) and create an account.

### 2. Create Products

**In Stripe Dashboard**:

1. Go to **Products** → **+ Add Product**
2. Create "Portfolio AI Pro"
   - Name: `Portfolio AI Pro`
   - Type: `Recurring`
   - Pricing: `$29/month`
   - Billing period: `Monthly`

### 3. Get API Keys

1. Go to **Developers** → **API Keys**
2. Copy:
   - **Publishable Key** (starts with `pk_live_`)
   - **Secret Key** (starts with `sk_live_`)
3. Add to `.env` and GitHub secrets

### 4. Setup Webhooks

1. Go to **Developers** → **Webhooks**
2. Click **+ Add endpoint**
3. URL: `https://app.yourdomain.com/webhooks/stripe`
4. Events: Select
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `charge.succeeded`
   - `charge.failed`
5. Copy **Signing secret** to `.env`

## Backend Implementation

### src/services/billing.py

```python
import stripe
from core.config import settings
from core.database import AsyncSessionLocal
from models.database import Tenant, Invoice, UsageMetric
from sqlalchemy import select, func
from datetime import datetime, timedelta

stripe.api_key = settings.stripe_secret_key

class BillingService:
    @staticmethod
    async def create_checkout_session(tenant_id: str, tier: str):
        """
        Create Stripe checkout session for tenant.
        """
        async with AsyncSessionLocal() as db:
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            tenant = await db.execute(stmt)
            tenant = tenant.scalar_one_or_none()
            
            if not tenant:
                return None
            
            # Get or create Stripe customer
            if not tenant.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=tenant.email,
                    name=tenant.name,
                    metadata={"tenant_id": tenant_id}
                )
                tenant.stripe_customer_id = customer.id
                await db.commit()
            
            # Pricing for tiers
            pricing = {
                "pro": "price_1Abc123Pro",  # Replace with your Stripe price ID
                "enterprise": None
            }
            
            if tier == "enterprise":
                # Contact sales
                return {"type": "enterprise", "email": "sales@yourdomain.com"}
            
            session = stripe.checkout.Session.create(
                customer=tenant.stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": pricing[tier],
                    "quantity": 1
                }],
                mode="subscription",
                success_url=f"https://app.yourdomain.com/dashboard?success=true",
                cancel_url=f"https://app.yourdomain.com/billing?cancel=true"
            )
            
            return {"checkout_url": session.url}
    
    @staticmethod
    async def handle_webhook(event: dict, db):
        """
        Handle Stripe webhook events.
        """
        event_type = event["type"]
        data = event["data"]["object"]
        
        if event_type == "customer.subscription.created" or event_type == "customer.subscription.updated":
            # Update tenant tier
            tier_mapping = {
                "price_1Abc123Pro": "pro",
                "price_1Abc123Enterprise": "enterprise"
            }
            
            tier = tier_mapping.get(data["items"]["data"][0]["price"]["id"], "free")
            
            stmt = select(Tenant).where(Tenant.stripe_customer_id == data["customer"])
            tenant = await db.execute(stmt)
            tenant = tenant.scalar_one_or_none()
            
            if tenant:
                tenant.tier = tier
                await db.commit()
        
        elif event_type == "customer.subscription.deleted":
            # Downgrade to free
            stmt = select(Tenant).where(Tenant.stripe_customer_id == data["customer"])
            tenant = await db.execute(stmt)
            tenant = tenant.scalar_one_or_none()
            
            if tenant:
                tenant.tier = "free"
                await db.commit()
    
    @staticmethod
    async def track_usage(tenant_id: str, tokens_used: int, db):
        """
        Track token usage for billing.
        """
        metric = UsageMetric(
            tenant_id=tenant_id,
            date=datetime.utcnow(),
            total_completion_tokens=tokens_used
        )
        db.add(metric)
        await db.commit()
    
    @staticmethod
    async def calculate_monthly_usage(tenant_id: str, db) -> int:
        """
        Calculate total tokens used this month.
        """
        month_ago = datetime.utcnow() - timedelta(days=30)
        
        stmt = select(func.sum(UsageMetric.total_completion_tokens)).where(
            (UsageMetric.tenant_id == tenant_id) &
            (UsageMetric.date > month_ago)
        )
        
        result = await db.execute(stmt)
        total = result.scalar() or 0
        return total
    
    @staticmethod
    async def calculate_overage(tenant_id: str, tokens_used: int, db) -> float:
        """
        Calculate overage cost if over tier limit.
        """
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = await db.execute(stmt)
        tenant = tenant.scalar_one_or_none()
        
        if not tenant:
            return 0.0
        
        tier_limits = {
            "free": 100000,
            "pro": 1000000,
            "enterprise": float('inf')
        }
        
        limit = tier_limits.get(tenant.tier, 100000)
        overage = max(0, tokens_used - limit)
        
        # Pricing: $0.01 per 1k tokens over limit
        overage_cost = (overage / 1000) * 0.01
        
        return overage_cost
    
    @staticmethod
    async def generate_invoice(tenant_id: str, db):
        """
        Generate monthly invoice.
        """
        month_start = datetime.utcnow().replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Get tier cost
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = await db.execute(stmt)
        tenant = tenant.scalar_one_or_none()
        
        tier_costs = {
            "free": 0,
            "pro": 29,
            "enterprise": 0  # Custom pricing
        }
        
        base_cost = tier_costs.get(tenant.tier, 0)
        
        # Get token usage
        usage = await BillingService.calculate_monthly_usage(tenant_id, db)
        overage_cost = await BillingService.calculate_overage(tenant_id, usage, db)
        
        total = base_cost + overage_cost
        
        invoice = Invoice(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            period_start=month_start,
            period_end=month_end,
            base_tier_cost=base_cost,
            overage_tokens=max(0, usage - tier_costs.get(tenant.tier, 100000)),
            overage_cost=overage_cost,
            total_amount=total,
            status="draft"
        )
        
        db.add(invoice)
        await db.commit()
        
        return invoice
```

### src/api/billing.py

```python
from fastapi import APIRouter, Depends, HTTPException
from core.database import get_db
from core.middleware import get_current_tenant
from models.database import Tenant
from services.billing import BillingService
from core.config import settings
import stripe

router = APIRouter(prefix="/api/billing", tags=["billing"])

@router.post("/checkout")
async def create_checkout(
    tier: str,
    tenant: Tenant = Depends(get_current_tenant),
    db = Depends(get_db)
):
    """Create Stripe checkout session"""
    
    if tier not in ["pro", "enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    result = await BillingService.create_checkout_session(tenant.id, tier, db)
    
    if result.get("type") == "enterprise":
        return {"message": "Contact sales", "email": result["email"]}
    
    return result

@router.get("/usage")
async def get_usage(
    tenant: Tenant = Depends(get_current_tenant),
    db = Depends(get_db)
):
    """Get tenant usage and billing info"""
    
    usage = await BillingService.calculate_monthly_usage(tenant.id, db)
    overage = await BillingService.calculate_overage(tenant.id, usage, db)
    
    tier_limits = {"free": 100000, "pro": 1000000, "enterprise": float('inf')}
    limit = tier_limits.get(tenant.tier, 100000)
    
    return {
        "tier": tenant.tier,
        "monthly_tokens_used": usage,
        "monthly_token_limit": limit,
        "percentage": (usage / limit * 100) if limit else 0,
        "overage_cost": overage,
        "estimated_total": (29 if tenant.tier == "pro" else 0) + overage
    }
```

### src/api/webhooks.py (Stripe)

```python
from fastapi import APIRouter, Request, HTTPException
from services.billing import BillingService
from core.database import get_db
import stripe
import json

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/stripe")
async def stripe_webhook(request: Request, db = Depends(get_db)):
    """Handle Stripe webhook events"""
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle event
    await BillingService.handle_webhook(event, db)
    
    return {"received": True}
```

## Frontend: Billing Page

**src/pages/BillingPage.tsx**:

```typescript
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export function BillingPage() {
  const { data: usage } = useQuery({
    queryKey: ['billing'],
    queryFn: async () => {
      const res = await api.get('/billing/usage');
      return res.data;
    },
  });

  const handleUpgrade = async (tier: string) => {
    const res = await api.post('/billing/checkout', { tier });
    if (res.data.checkout_url) {
      window.location.href = res.data.checkout_url;
    }
  };

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-3xl font-bold">Billing & Subscription</h1>
      
      <div className="grid gap-4 md:grid-cols-3">
        <Card className={usage?.tier === 'free' ? 'border-2 border-primary' : ''}>
          <CardHeader>
            <CardTitle>Free</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-2xl font-bold">$0/month</div>
            <ul className="text-sm space-y-2">
              <li>✓ 100k tokens/month</li>
              <li>✓ 1 Knowledge Base</li>
              <li>✗ No API access</li>
            </ul>
            {usage?.tier === 'free' && (
              <Button disabled>Current Plan</Button>
            )}
          </CardContent>
        </Card>

        <Card className={usage?.tier === 'pro' ? 'border-2 border-primary' : ''}>
          <CardHeader>
            <CardTitle>Pro</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-2xl font-bold">$29/month</div>
            <ul className="text-sm space-y-2">
              <li>✓ 1M tokens/month</li>
              <li>✓ 10 Knowledge Bases</li>
              <li>✓ API access</li>
              <li>✓ Email support</li>
            </ul>
            <Button 
              onClick={() => handleUpgrade('pro')}
              disabled={usage?.tier === 'pro'}
            >
              {usage?.tier === 'pro' ? 'Current Plan' : 'Upgrade'}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Enterprise</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-2xl font-bold">Custom</div>
            <ul className="text-sm space-y-2">
              <li>✓ Unlimited tokens</li>
              <li>✓ White-label</li>
              <li>✓ 99.9% SLA</li>
              <li>✓ Dedicated support</li>
            </ul>
            <Button 
              onClick={() => handleUpgrade('enterprise')}
            >
              Contact Sales
            </Button>
          </CardContent>
        </Card>
      </div>

      {usage && (
        <Card>
          <CardHeader>
            <CardTitle>Current Usage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <p className="text-sm text-muted-foreground">Tokens Used</p>
                <p className="text-2xl font-bold">
                  {(usage.monthly_tokens_used / 1000).toFixed(0)}k / {(usage.monthly_token_limit / 1000).toFixed(0)}k
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Estimated Cost</p>
                <p className="text-2xl font-bold">
                  ${usage.estimated_total.toFixed(2)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

## Testing Stripe Locally

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhook events to local machine
stripe listen --forward-to localhost:8000/webhooks/stripe

# Trigger test event
stripe trigger customer.subscription.created
```

---

**Next Steps**: Refer to `07-checklist.md` for launch preparation.
