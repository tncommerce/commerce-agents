import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Component Showcase",
  robots: {
    index: false,
    follow: false,
    nocache: true,
  },
};

export default function ShowcaseLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
