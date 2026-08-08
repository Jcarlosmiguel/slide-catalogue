FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# mariadb-client provides mariadb-dump, used by backup_catalogue.py to create
# on-demand backups from inside this container. libvips42 is the native
# library pyvips binds to - OpenSlide/TiffSlide can't open some real Leica
# .scn (multiple dissimilar main images) or Hamamatsu .ndpi (Z-stack)
# files; vips reads them directly instead. Not yet wired into
# populate_new_slide_thumbnails.py's automated path (still a manual
# fallback as of 2026-08-08) - installed ahead of that so the image is
# ready when it is.
RUN apt-get update && \
    apt-get install -y --no-install-recommends mariadb-client libvips42 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
