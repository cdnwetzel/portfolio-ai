# Frontend Setup Guide

## React Project Structure

```
frontend/
├── src/
│   ├── index.tsx
│   ├── App.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx       # Main control panel
│   │   ├── LoginPage.tsx
│   │   ├── SignupPage.tsx
│   │   └── ChatPage.tsx
│   ├── components/
│   │   ├── ui/                 # Shadcn UI components
│   │   ├── Sidebar.tsx
│   │   ├── Header.tsx
│   │   └── ChatBox.tsx
│   ├── lib/
│   │   ├── api.ts              # Axios client
│   │   ├── hooks.ts            # Custom React hooks
│   │   └── utils.ts
│   ├── styles/
│   │   └── globals.css
│   └── types/
│       └── index.ts            # TypeScript types
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## Step 1: Setup & Dependencies

```bash
# Create Vite project
npm create vite@latest frontend -- --template react-ts

# Navigate to frontend
cd frontend

# Install dependencies
npm install

# UI Library
npm install @radix-ui/react-dialog
npm install -D shadcn-ui

# API Client
npm install axios @tanstack/react-query

# Routing
npm install react-router-dom

# Styling
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# Utilities
npm install clsx date-fns

# Dev dependencies
npm install -D typescript @types/react @types/node
```

## Step 2: Configure Shadcn UI

**tailwind.config.ts**:

```typescript
import type { Config } from "tailwindcss"

const config: Config = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
```

## Step 3: API Client Setup

**src/lib/api.ts**:

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Auto-inject JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle token refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
```

## Step 4: Custom Hooks

**src/lib/hooks.ts**:

```typescript
import { useQuery, useMutation } from '@tanstack/react-query';
import api from './api';

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const res = await api.get('/dashboard');
      return res.data;
    },
  });
}

export function useLogin() {
  return useMutation({
    mutationFn: async (credentials: { email: string; password: string }) => {
      const res = await api.post('/auth/login', credentials);
      localStorage.setItem('access_token', res.data.access_token);
      return res.data;
    },
  });
}

export function useSignup() {
  return useMutation({
    mutationFn: async (data: { email: string; company_name: string; password: string }) => {
      const res = await api.post('/auth/signup', data);
      localStorage.setItem('access_token', res.data.access_token);
      return res.data;
    },
  });
}
```

## Step 5: Dashboard Page

**src/pages/Dashboard.tsx**:

```typescript
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';

export function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['tenantStats'],
    queryFn: async () => {
      const res = await api.get('/dashboard');
      return res.data;
    },
  });

  if (isLoading) return <DashboardSkeleton />;
  if (error) return <div className="text-red-500">Failed to load dashboard.</div>;

  return (
    <div className="space-y-6 p-8">
      <h1 className="text-3xl font-bold tracking-tight">Overview</h1>
      
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Tokens Used</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data.usage_this_month.tokens.toLocaleString()}
            </div>
            <Progress 
              value={data.usage_this_month.percentage_of_limit} 
              className="mt-2" 
            />
            <p className="text-xs text-muted-foreground mt-1">
              {data.usage_this_month.percentage_of_limit.toFixed(1)}% of monthly limit
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Active Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data.usage_this_month.sessions}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Subscription Tier</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">
              {data.tier}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Next bill: {new Date(data.next_billing_date).toLocaleDateString()}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="p-8 space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 md:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
    </div>
  );
}
```

## Step 6: Login Page

**src/pages/LoginPage.tsx**:

```typescript
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLogin } from '../lib/hooks';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const { mutate: login, isPending, error } = useLogin();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login(
      { email, password },
      {
        onSuccess: () => navigate('/dashboard'),
        onError: (err) => console.error('Login failed:', err),
      }
    );
  };

  return (
    <div className="flex items-center justify-center h-screen bg-muted">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Login to Portfolio AI</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium">Email</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
            <div>
              <label className="text-sm font-medium">Password</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            {error && <div className="text-red-500 text-sm">Login failed</div>}
            <Button 
              type="submit" 
              className="w-full" 
              disabled={isPending}
            >
              {isPending ? 'Logging in...' : 'Login'}
            </Button>
          </form>
          <p className="text-center text-sm mt-4">
            Don't have an account?{' '}
            <a href="/signup" className="text-blue-600">Sign up</a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
```

## Step 7: Signup Page

**src/pages/SignupPage.tsx**:

```typescript
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSignup } from '../lib/hooks';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

export function SignupPage() {
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const { mutate: signup, isPending, error } = useSignup();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    signup(
      { email, company_name: company, password },
      {
        onSuccess: () => navigate('/dashboard'),
        onError: (err) => console.error('Signup failed:', err),
      }
    );
  };

  return (
    <div className="flex items-center justify-center h-screen bg-muted">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Create Your Account</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium">Email</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
            <div>
              <label className="text-sm font-medium">Company Name</label>
              <Input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme Inc"
                required
              />
            </div>
            <div>
              <label className="text-sm font-medium">Password</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            {error && <div className="text-red-500 text-sm">Signup failed</div>}
            <Button 
              type="submit" 
              className="w-full" 
              disabled={isPending}
            >
              {isPending ? 'Creating account...' : 'Sign Up'}
            </Button>
          </form>
          <p className="text-center text-sm mt-4">
            Already have an account?{' '}
            <a href="/login" className="text-blue-600">Login</a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
```

## Step 8: App Router

**src/App.tsx**:

```typescript
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { Dashboard } from './pages/Dashboard';

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/" element={<LoginPage />} />
        </Routes>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
```

## Step 9: Build & Deploy

```bash
# Development
npm run dev

# Production build
npm run build

# Preview build
npm run preview
```

## Environment Variables

**Create `.env.local`**:

```
VITE_API_URL=http://localhost:8000
VITE_STRIPE_PUBLIC_KEY=pk_test_xxxxx
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Axios 401 on every request | Check JWT in localStorage, token may be expired |
| CORS errors | Verify FastAPI CORS config includes your frontend URL |
| Components not styled | Run `npx shadcn-ui@latest add <component>` to install UI components |
| React Router not working | Ensure BrowserRouter wraps your routes |

---

**Next Steps**: Refer to `04-infrastructure.md` for deployment setup.
