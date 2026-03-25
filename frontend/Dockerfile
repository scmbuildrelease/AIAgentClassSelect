FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Expose frontend port
EXPOSE 3000

# Start frontend dev server
CMD ["npm", "start"]
