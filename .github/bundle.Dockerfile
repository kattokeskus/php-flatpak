# Flatpak bundles of every architecture as an image, for storing build results
# in the registry.
FROM scratch
COPY *.flatpak /
