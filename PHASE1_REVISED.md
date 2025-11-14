# 🎯 Phase 1 - REVISED MVP Checklist

**Goal:** Working demo that shows Instagram post optimization value in ~8-10 hours

## Demo User Flow
```
User → Connect Instagram → Sync Posts → Train Model → View Best Posting Time Predictions
```

---

## ✅ ALREADY COMPLETED (65%)

### Infrastructure & Backend Core
- ✅ Database models (7 tables with relationships)
- ✅ FastAPI application setup
- ✅ Instagram OAuth 2.0 flow (authorize → callback → token exchange)
- ✅ Historical post sync with pagination
- ✅ Content analysis (hashtags, emojis, engagement)
- ✅ Account management API endpoints
- ✅ ML module structure (all files scaffolded)
- ✅ Docker Compose configuration

---

## 🚀 PHASE 1 MVP - REMAINING WORK

### 1. ML Model Implementation (CRITICAL) - ~4 hours
**Status:** Structure exists, need logic

#### 1.1 Feature Engineering
- [ ] `ml/features/temporal_features.py` - Extract time-based features
  - Hour of day, day of week, is_weekend
  - Time since last post
- [ ] `ml/features/content_features.py` - Extract content features
  - Caption length, hashtag count, emoji count
  - Media type (image/video/carousel)
- [ ] `ml/features/feature_engineering.py` - Combine all features
  - Create feature matrix for training

#### 1.2 Model Training
- [ ] `ml/training/data_loader.py` - Load posts from database
  - Query posts with engagement metrics
  - Convert to pandas DataFrame
- [ ] `ml/training/preprocessor.py` - Prepare data for XGBoost
  - Handle missing values
  - Encode categorical variables
  - Split train/test
- [ ] `ml/training/trainer.py` - Train XGBoost model
  - Basic hyperparameters (no tuning)
  - Train on engagement rate as target
  - Save model to disk

#### 1.3 Prediction Generation
- [ ] `ml/prediction/predictor.py` - Generate predictions
  - Load trained model
  - Predict engagement for different time slots
  - Return top 3 best times
- [ ] `ml/service.py` - Connect everything together
  - Orchestrate training pipeline
  - Orchestrate prediction pipeline

---

### 2. API Integration (CRITICAL) - ~1 hour

- [ ] `api/endpoints/predictions.py` - Wire up ML service
  - `POST /predictions/train` - Trigger model training
  - `GET /predictions/latest` - Get best posting times
- [ ] Test endpoints with Postman/curl

---

### 3. Docker & Integration Testing (HIGH) - ~1-2 hours

- [ ] Test `docker-compose up` starts all services
- [ ] Verify database initializes properly
- [ ] Run Alembic migrations
- [ ] Test one complete OAuth flow manually
- [ ] Test post sync for one account
- [ ] Test model training with real data

---

### 4. Minimal Frontend (MEDIUM) - ~3-4 hours

#### 4.1 Setup
- [ ] Create Next.js app in `frontend/` directory
- [ ] Install dependencies (React, Tailwind, shadcn/ui)
- [ ] Setup API client for backend

#### 4.2 Pages (Keep it SIMPLE!)
- [ ] Landing page with "Connect Instagram" button
- [ ] Dashboard page showing:
  - ✅ Connected account info
  - ✅ Recent posts count
  - ✅ "Train Model" button
  - ✅ Best posting times (simple list/card)
  - ✅ Simple bar chart of predicted engagement by hour

#### 4.3 Integration
- [ ] OAuth redirect handling
- [ ] Call `/predictions/train` endpoint
- [ ] Call `/predictions/latest` and display results

---

## ❌ DEFERRED TO PHASE 2

These are **NOT needed** for Phase 1 demo:

- ⏸️ Scheduled posts feature (complete implementation)
- ⏸️ Advanced ML features (hyperparameter tuning, versioning)
- ⏸️ Multiple frontend views/pages
- ⏸️ Beautiful UI polish
- ⏸️ Advanced data visualization
- ⏸️ Comprehensive error handling
- ⏸️ Performance optimization
- ⏸️ Automated testing suite
- ⏸️ Advanced confidence metrics

---

## 📊 Estimated Time Breakdown

| Task | Time | Priority |
|------|------|----------|
| Feature Engineering | 1.5h | CRITICAL |
| Model Training | 1.5h | CRITICAL |
| Prediction Logic | 1h | CRITICAL |
| API Integration | 1h | CRITICAL |
| Docker Testing | 1-2h | HIGH |
| Frontend Setup | 1h | MEDIUM |
| Frontend Pages | 2-3h | MEDIUM |
| **TOTAL** | **9-11h** | |

---

## 🎬 Recommended Work Order

1. **ML Implementation** (get predictions working first)
   - Feature engineering → Training → Prediction
2. **API Integration** (connect ML to endpoints)
3. **Docker Test** (verify backend works end-to-end)
4. **Frontend** (build visual layer last)

---

## ✨ Phase 1 Success Criteria

**Demo is successful if:**
1. ✅ User can connect their Instagram account
2. ✅ System syncs their posts automatically
3. ✅ User can trigger model training
4. ✅ System shows "Best time to post: [time] with [confidence]"
5. ✅ Shows simple visualization of predictions

**That's it!** Everything else is polish for Phase 2.

---

## 💡 Key Principles for Phase 1

- **Simple beats perfect** - Basic XGBoost with default params is fine
- **Manual beats automated** - User clicks "Train" button is fine
- **Working beats beautiful** - Ugly dashboard that works > beautiful one that doesn't
- **Defer everything non-critical** - Focus on the core value proposition

---

**Last Updated:** 2025-11-13
**Current Status:** Infrastructure complete, ML implementation in progress
