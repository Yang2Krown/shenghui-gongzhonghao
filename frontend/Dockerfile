# 使用Node.js镜像
FROM node:18-alpine as development

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV NODE_ENV=development

# 安装依赖
COPY package.json ./
RUN npm install

# 复制源代码
COPY . .

# 暴露端口
EXPOSE 3000

# 开发模式启动
CMD ["npm", "run", "dev"]

# 生产环境构建
FROM node:18-alpine as build

WORKDIR /app

# 安装依赖
COPY package.json ./
RUN npm install

# 构建应用
COPY . .
RUN npm run build

# 生产环境
FROM nginx:alpine as production

# 复制构建产物
COPY --from=build /app/dist /usr/share/nginx/html

# 复制nginx配置
COPY nginx.conf /etc/nginx/nginx.conf

# 暴露端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]