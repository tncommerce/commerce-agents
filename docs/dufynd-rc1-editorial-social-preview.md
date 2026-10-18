# DUFYND RC1 – original and truthful link-preview art (Draft RESET37)

**Objective:** The live Rabanne 1 Million Eau de Toilette 100 ml page currently
has no rights-verified reusable product photo. Its social metadata consequently
renders no link image, although social discovery matters for first-money traffic.
This is a reversible discovery improvement, **not** a fix for the still-subpar
Premium CGI Hero and not a production release.

An original editorial abstract amber-light 1200x630 PNG is rendered at build
and dev startup from the in-repo SVG source (no external image, license grant,
paid API, fonts, credits or network). It uses exact variant information:
Rabanne, 1 Million, Eau de Toilette, 100 ml. It has **no product photo**,
logo imitation, price, offer stock, shopping checkout or claimed sale.
The PNG is a generated build asset, not a new upstream photo source.

The actual fragrance metadata selects this *only* if the exact RC1 product
has no approved originalPhotoFor() source. When a rights-verified original is
available, it wins; any other product without an original remains without
a social image. Product JSON-LD image continues to require verified
originalPhotoFor(): an editorial card NEVER becomes a product photo.
Global indexability, exact source rights, attribution, offer cards, client
analytics and Consent are unchanged.

Deterministic tests check file dimensions, source facts, SVG isolation and
actual generateMetadata behavior for RC1/no image, another product/no image,
and an authenticated original photo. Test runs through existing dev/prebuild;
no new service or dependency. The new original visual direction remains
Owner quality-gated. It is not a claim that the full site is 9.5/10.
