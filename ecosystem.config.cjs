module.exports = {
  apps: [
    {
      name: 'medisafe-backend',
      cwd: '/home/work/.openclaw/workspace/medisafe/backend',
      script: 'uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8010 --workers 2',
      interpreter: 'python3',
      env: {
        DATABASE_URL: 'postgresql://medisafe:medisafe_secret_2024@localhost:5432/medisafe',
        REDIS_URL: 'redis://localhost:6379/0',
        SECRET_KEY: 'medisafe-prod-secret-key-change-this-in-real-production-2024',
        ALGORITHM: 'HS256',
        ACCESS_TOKEN_EXPIRE_MINUTES: '480',
        APP_NAME: 'MediSafe Clinic',
        DEBUG: 'false',
      },
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
    },
  ],
}
