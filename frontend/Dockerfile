FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i 's|pid .*;|pid /tmp/nginx.pid;|; s|^user .*;||' /etc/nginx/nginx.conf \
    && mkdir -p /var/cache/nginx /etc/nginx/templates \
    && chown -R nginx:nginx /var/cache/nginx /etc/nginx/conf.d /etc/nginx/templates
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY 15-resolver.envsh /docker-entrypoint.d/15-resolver.envsh
RUN chmod +x /docker-entrypoint.d/15-resolver.envsh
COPY index.html app.js styles.css /usr/share/nginx/html/
COPY assets/ /usr/share/nginx/html/assets/
USER nginx
EXPOSE 8080
