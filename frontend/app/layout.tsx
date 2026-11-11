import type { Metadata } from "next";
import { Azeret_Mono, Besley, Hanken_Grotesk } from "next/font/google";
import { SkipLink } from "@/components/skip-link";
import Providers from "./providers";
import "./globals.css";

const besley = Besley({ weight: "500", subsets: ["latin"], variable: "--resiq-besley" });
const hanken = Hanken_Grotesk({ weight: ["400", "600"], subsets: ["latin"], variable: "--resiq-hanken" });
const azeret = Azeret_Mono({ weight: ["400", "600"], subsets: ["latin"], variable: "--resiq-azeret" });

export const metadata: Metadata = {
  title: { default: "Resiq | From resibo to columnar book", template: "%s | Resiq" },
  description: "Turn a receipt photo into a reviewed entry in your expense journal.",
  icons: { icon: "/resiq.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en-PH" className={besley.variable + " " + hanken.variable + " " + azeret.variable}>
    <body><SkipLink /><Providers>{children}</Providers></body>
  </html>;
}
