FROM node:18-alpine

WORKDIR /app

# Копируем package.json и устанавливаем зависимости
COPY package.json package-lock.json* ./
RUN npm install

# Копируем исходные файлы
COPY src/ /app/src/
COPY webpack.config.js /app/
COPY babel.config.js /app/
COPY postcss.config.js /app/

# Собираем проект
RUN npm run build

# Запуск сервера через npm start
CMD ["npm", "start"]