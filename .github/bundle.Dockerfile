# A flatpak bundle as an image, for storing build results in the registry.
FROM scratch
ARG BUNDLE
COPY ${BUNDLE} /
