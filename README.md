# Samora Ledger Tech

Enterprise banking transaction analytics and action engine MVP.

## Project source

The complete MVP source archive is available from the project workspace as `samora-ledger-tech-mvp.zip`. It contains the Next.js frontend, FastAPI analytics backend, Supabase schema, synthetic data seeder, CI workflow, and deployment guidance.

## Stack

- Next.js App Router, TypeScript, Tailwind CSS, Recharts
- Supabase PostgreSQL, Auth, and Row Level Security
- Python 3.11, FastAPI, Pandas, NumPy, scikit-learn, XGBoost
- Vercel (frontend) and Render (API)

## Validation performed

- Backend tests: 2 passed
- Python compilation: passed
- FastAPI application import and route registration: passed
- Synthetic data generation: 1,000 customers and 218,784 transactions

The predictive scores currently use synthetic proxy labels and are for demonstration only. Do not use them for real financial decisions without validated outcome data, calibration, fairness testing, governance, and human oversight.

See `DEPLOYMENT_CHECKLIST.md` in the full source archive for deployment steps.