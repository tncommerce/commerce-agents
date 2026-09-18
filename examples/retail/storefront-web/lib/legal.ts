// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

const env = (name: string) => process.env[name]?.trim() ?? "";

export const legal = {
  businessName: env("NEXT_PUBLIC_LEGAL_BUSINESS_NAME") || "TNCommerce",
  ownerName: env("NEXT_PUBLIC_LEGAL_OWNER_NAME"),
  street: env("NEXT_PUBLIC_LEGAL_STREET"),
  postcode: env("NEXT_PUBLIC_LEGAL_POSTCODE"),
  city: env("NEXT_PUBLIC_LEGAL_CITY"),
  email: env("NEXT_PUBLIC_LEGAL_EMAIL"),
};

export const legalReady = Boolean(
  legal.businessName &&
    legal.ownerName &&
    legal.street &&
    legal.postcode &&
    legal.city &&
    legal.email,
);

export const legalLocation = [legal.postcode, legal.city].filter(Boolean).join(" ");
