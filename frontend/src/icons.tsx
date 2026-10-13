import type { SVGProps } from "react";

export function BrandLogo({ size = 34, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <defs>
        <linearGradient id="dq-brand-bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#1a73e8" />
          <stop offset="100%" stopColor="#1558b0" />
        </linearGradient>
        <linearGradient id="dq-brand-badge" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#34a853" />
          <stop offset="100%" stopColor="#137333" />
        </linearGradient>
        <filter id="dq-brand-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1.2" stdDeviation="1" floodColor="#0b2e59" floodOpacity="0.25" />
        </filter>
      </defs>

      {/* Main Base Badge */}
      <rect width="32" height="32" rx="8" fill="url(#dq-brand-bg)" />

      {/* Structured Dataset Stack Layers */}
      <rect x="5.5" y="6" width="21" height="4.5" rx="1.5" fill="#ffffff" fillOpacity="0.38" />
      <rect x="5.5" y="12" width="13.5" height="3.2" rx="1.2" fill="#ffffff" fillOpacity="0.25" />
      <rect x="5.5" y="16.5" width="10.5" height="3.2" rx="1.2" fill="#ffffff" fillOpacity="0.25" />
      <rect x="5.5" y="21" width="12" height="3.2" rx="1.2" fill="#ffffff" fillOpacity="0.25" />

      {/* Quality Audit Validation Seal */}
      <g filter="url(#dq-brand-shadow)">
        <circle cx="21.5" cy="20.5" r="7" fill="url(#dq-brand-badge)" stroke="#ffffff" strokeWidth="1.6" />
        <path d="M18.5 20.5l2 2 4-4" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

export function DashboardNavIcon({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <rect x="2.5" y="2.5" width="6.5" height="6.5" rx="1.8" />
      <rect x="11" y="2.5" width="6.5" height="4.5" rx="1.8" />
      <rect x="2.5" y="11" width="6.5" height="6.5" rx="1.8" />
      <rect x="11" y="9" width="6.5" height="8.5" rx="1.8" />
      <path d="M4.5 5.8h2.5M4.5 14.2h2.5M13 13.2h2.5M13 15.2h1.5" strokeWidth="1.3" />
    </svg>
  );
}

export function DatasetsNavIcon({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <rect x="2.5" y="3" width="15" height="14" rx="2" />
      <path d="M2.5 7.5h15" />
      <path d="M8 7.5v9.5" />
      <circle cx="5.2" cy="5.2" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="8" cy="5.2" r="0.75" fill="currentColor" stroke="none" />
      <path d="M10.8 11.2h4.4M10.8 14h3.2" strokeWidth="1.3" />
    </svg>
  );
}

export function FindingsNavIcon({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M7 3.2h6a1 1 0 0 1 1 1V4.8H6V4.2a1 1 0 0 1 1-1Z" />
      <rect x="3.5" y="4.5" width="13" height="13" rx="2" />
      <path d="M6.5 8.8h7M6.5 11.8h3.8" strokeWidth="1.3" />
      <path d="M12 14.2l1.6 1.6 3.2-3.2" strokeWidth="1.7" />
    </svg>
  );
}

export function ReferenceNavIcon({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <rect x="2.8" y="3" width="6.2" height="5.2" rx="1.5" />
      <rect x="11" y="3" width="6.2" height="5.2" rx="1.5" />
      <rect x="6.9" y="12" width="6.2" height="5.2" rx="1.5" />
      <path d="M5.9 8.2v2a1 1 0 0 0 1 1h6.2a1 1 0 0 0 1-1v-2" />
      <path d="M10 11.2v0.8" />
    </svg>
  );
}

export function SettingsNavIcon({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M2.8 5.5h7.4M14.5 5.5h2.7" />
      <circle cx="12.2" cy="5.5" r="2" />
      <path d="M2.8 14.5h4.2M11.5 14.5h5.7" />
      <circle cx="9" cy="14.5" r="2" />
      <path d="M2.8 10h10.2M16.8 10h0.4" />
      <circle cx="14.8" cy="10" r="2" />
    </svg>
  );
}

export function PeopleNavIcon({ size = 20, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <circle cx="7.5" cy="6" r="3" />
      <path d="M2.5 17v-1.5a5 5 0 0 1 10 0V17M13 3.2a3 3 0 0 1 0 5.6M15 11a4.5 4.5 0 0 1 2.5 4V17" />
    </svg>
  );
}

export function TrashIcon({ size = 18, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d="M3 5h14M7 5V3h6v2M5 5l.8 12h8.4L15 5M8 8v6M12 8v6" /></svg>;
}

export function LogoutIcon({ size = 16, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M8 3H4a1.5 1.5 0 0 0-1.5 1.5v11A1.5 1.5 0 0 0 4 17h4M7.5 10h10M14 6.5l3.5 3.5-3.5 3.5" />
    </svg>
  );
}

export function PlusIcon({ size = 18, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

export function SearchIcon({ size = 16, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.5" y2="16.5" />
    </svg>
  );
}

export function ChevronRightIcon({ size = 18, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export function ChevronDownIcon({ size = 16, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

export function ArrowLeftIcon({ size = 16, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </svg>
  );
}

export function ArrowRightIcon({ size = 16, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

export function CheckIcon({ size = 16, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function UploadCloudIcon({ size = 24, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

export function RefreshIcon({ size = 24, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
    </svg>
  );
}

export function ShieldCheckIcon({ size = 15, ...props }: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <polyline points="9 12 11 14 15 10" />
    </svg>
  );
}
