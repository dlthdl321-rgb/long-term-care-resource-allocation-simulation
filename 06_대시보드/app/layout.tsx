import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

const title = "돌봄자원 랩 | 장기요양 자원배치 의사결정 시뮬레이터";
const description =
  "76개 농촌 군의 장기요양 수요·기관·인력·정원을 결합해 공급격차를 진단하고 자원배치 전략을 비교하는 공공데이터 분석 프로젝트";

export async function generateMetadata(): Promise<Metadata> {
  const incoming = await headers();
  const host =
    incoming.get("x-forwarded-host") ?? incoming.get("host") ?? "localhost:3000";
  const protocol =
    incoming.get("x-forwarded-proto") ?? (host.includes("localhost") ? "http" : "https");
  const image = `${protocol}://${host}/og.png`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      images: [{ url: image, width: 1680, height: 945, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
