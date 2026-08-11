# Social preview asset

- Source: `social-preview.svg`
- Upload file: `social-preview.png`
- Size: 1280 × 640 pixels

On macOS, regenerate the PNG after editing the SVG:

```console
sips -s format png assets/social-preview.svg --out assets/social-preview.png
```

GitHub does not expose a public REST or GraphQL mutation for uploading a repository social preview. A repository administrator must open:

```text
Repository → Settings → General → Social preview → Edit → Upload an image
```

Upload `assets/social-preview.png`, save, then share the repository URL once to verify the generated Open Graph image.
