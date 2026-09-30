# Nipuna LMS — Staging accounts

Created by `flask --app app seed-dev` in the dev database (`nipunalms-dev`). **Never use these in production.**

Password for every account: **`Nipuna-staging-1`**

## Staff

| Role | Guntur (NIT-GNT, branch 1) | Vijayawada (NIT-VIJ, branch 2) |
|---|---|---|
| Founder / CEO | `founder@nipuna.test` (company-wide) | |
| Super Admin | `admin@nipuna.test` (company-wide) | |
| Branch Manager | `bm.gnt@nipuna.test` | `bm.vij@nipuna.test` |
| Academic Coordinator | `coordinator.gnt@nipuna.test` | `coordinator.vij@nipuna.test` |
| Trainer | `trainer.g1@nipuna.test` (Trainer R. Sample), `trainer.g2@nipuna.test` (Trainer M. Demo), `trainer.g3@nipuna.test` (Trainer K. Sample) | `trainer.v1@nipuna.test` (Trainer S. Example), `trainer.v2@nipuna.test` (Trainer P. Demo) |

## Students

Students sign in with their **Student ID** (or email, when they have one) — never a mobile number.

| Student ID | Name | State |
|---|---|---|
| `NIT-STU-2026-004182` | Anvitha K. | Activated — the prototype's sample student (combo, separately purchased and complimentary enrolments) |
| `NIT-STU-2026-004183`…`004185` | Sample Learners G, H, I | Activated |
| `NIT-STU-2026-004186` | Sample Learner J. | **Activation Pending** — `seed-dev` prints its one-time link `/activate?token=…` |
| `NIT-STU-2026-004187`… | Sample Learners A–F and batch fillers | Activated |

## Service key

The CRM integration endpoints (`/api/v1/integrations/crm/*`) take `X-Service-Key: dev-crm-service-key` in development (`CRM_SERVICE_KEY` in `backend/.env`).
