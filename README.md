# 🏦 Payment Platform — Architecture Microservices

Plateforme d'agrégation de paiement type CinetPay pour l'Afrique de l'Ouest.

## 🏗️ Services

| Service         | Port | Description                                     |
|-----------------|------|-------------------------------------------------|
| auth-service    | 8001 | Authentification JWT + gestion utilisateurs     |
| payment-service | 8002 | Traitement paiements (Orange Money, MTN, Wave)  |
| wallet-service  | 8003 | Portefeuilles électroniques + ledger            |
| fraud-service   | 8004 | Détection de fraude en temps réel               |
| RabbitMQ        | 5672/15672 | File de messages entre services           |
| Redis           | 6379 | Cache + sessions + blacklist                    |
| PostgreSQL      | 5432 | Base de données principale                      |

## 🚀 Démarrage rapide

```bash
# 1. Configurer les variables d'environnement (OBLIGATOIRE)
cp auth-service/.env.example    auth-service/.env
cp payment-service/.env.example payment-service/.env
cp wallet-service/.env.example  wallet-service/.env
cp fraud-service/.env.example   fraud-service/.env

# Éditer chaque .env et renseigner les vraies clés API + SECRET_KEY

# 2. Lancer tous les services
docker-compose up --build -d

# 3. Vérifier les services
curl http://localhost:8001/health   # auth
curl http://localhost:8002/health   # payment
curl http://localhost:8003/health   # wallet
curl http://localhost:8004/health   # fraud

# Interface RabbitMQ Management
# http://localhost:15672  (rabbit_user / rabbit_pass)
```

## 🔐 Variables d'environnement importantes

| Variable              | Service         | Description                              |
|-----------------------|-----------------|------------------------------------------|
| `SECRET_KEY`          | auth-service    | Clé JWT (min. 32 chars, aléatoire)       |
| `WEBHOOK_SECRET`      | payment-service | Secret HMAC pour valider les callbacks   |
| `ORANGE_MONEY_API_KEY`| payment-service | Clé API Orange Money                     |
| `MTN_MOMO_API_KEY`    | payment-service | Clé API MTN MoMo                         |
| `WAVE_API_KEY`        | payment-service | Clé API Wave                             |

## 📡 API Principales

### Auth Service (port 8001)
- `POST /api/v1/auth/register`  — Créer un compte *(max 5 req/min/IP)*
- `POST /api/v1/auth/login`     — Se connecter *(max 5 req/min/IP)*
- `POST /api/v1/auth/refresh`   — Rafraîchir le token
- `POST /api/v1/auth/logout`    — Se déconnecter
- `POST /api/v1/auth/verify`    — Vérifier un token

### Payment Service (port 8002)
- `POST /api/v1/payment/create`   — Créer un paiement
- `POST /api/v1/payment/verify`   — Vérifier un paiement
- `GET  /api/v1/transactions`     — Lister les transactions
- `POST /api/v1/webhook/callback` — Callback opérateurs *(signature HMAC vérifiée)*

### Wallet Service (port 8003)
- `POST /api/v1/wallets/`                   — Créer un wallet
- `GET  /api/v1/wallets/{owner_id}`         — Voir un wallet
- `GET  /api/v1/wallets/{owner_id}/balance` — Solde (avec cache Redis)
- `POST /api/v1/wallets/{wallet_id}/credit` — Créditer
- `POST /api/v1/wallets/{wallet_id}/debit`  — Débiter
- `GET  /api/v1/wallets/{wallet_id}/ledger` — Historique

### Fraud Service (port 8004)
- `POST  /api/v1/fraud/analyze`          — Analyser une transaction
- `GET   /api/v1/fraud/logs`             — Logs de fraude
- `PATCH /api/v1/fraud/logs/{id}/confirm`— Confirmer une fraude
- `POST  /api/v1/fraud/blacklist/add`    — Blacklister un numéro/IP

## 🔄 Flux de paiement

```
Client → POST /payment/create
       → Transaction créée (status: pending)
       → RabbitMQ publie "payment.created"
       → fraud-service consomme → analyse fraude
       → Appel opérateur (Orange/MTN/Wave)
       → RabbitMQ publie "payment.success" ou "payment.failed"
       → wallet-service consomme → crédite le wallet du marchand
```

## 🛡️ Sécurité

- **JWT** avec access token (30 min) + refresh token rotatif (7 jours)
- **Blacklist Redis** des tokens révoqués à la déconnexion
- **Rate limiting** : 5 req/min sur login et register (anti-brute-force)
- **Signature HMAC-SHA256** vérifiée sur les webhooks opérateurs
- **Bcrypt** pour le hachage des mots de passe

## 🔁 Résilience

- **Réconciliation automatique** : les transactions bloquées en `PROCESSING`
  depuis plus de 10 minutes sont relancées toutes les 5 minutes
- **Idempotence** : un paiement déjà traité ne sera pas recrédité deux fois
- **Reconnexion automatique** RabbitMQ (backoff 5s)
- **Pool PgBouncer-ready** : `pool_pre_ping=True` sur SQLAlchemy

## 🔒 Webhook — Configuration opérateurs

Pour Orange Money, MTN et Wave, configurez le callback URL :
```
http://votre-domaine.com/api/v1/webhook/callback
```
Et renseignez la même valeur dans `WEBHOOK_SECRET` (payment-service/.env)
que dans la console développeur de l'opérateur.

L'entête attendu : `X-Signature: sha256=<hmac_hex>` ou `X-Webhook-Signature`.
