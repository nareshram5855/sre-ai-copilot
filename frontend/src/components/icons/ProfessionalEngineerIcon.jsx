/** IT professional engineer avatar — spectacles, collared shirt. */
export function ProfessionalEngineerIcon({ size = 24, className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* Collar / shirt */}
      <path
        d="M6 20.5h12v1.5H6z"
        fill="currentColor"
        opacity="0.35"
      />
      <path
        d="M9.5 17.5 L12 20 L14.5 17.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.55"
      />
      <path
        d="M7 17.5 C8 15.5 10 14.5 12 14.5 C14 14.5 16 15.5 17 17.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        fill="none"
        opacity="0.5"
      />

      {/* Neck */}
      <rect x="10" y="13.5" width="4" height="2.5" rx="1" fill="currentColor" opacity="0.25" />

      {/* Face */}
      <ellipse cx="12" cy="10.2" rx="5.2" ry="5.8" fill="currentColor" opacity="0.18" />
      <ellipse
        cx="12"
        cy="10.2"
        rx="5.2"
        ry="5.8"
        stroke="currentColor"
        strokeWidth="1.15"
        opacity="0.85"
      />

      {/* Hair */}
      <path
        d="M6.8 10.2 C7 6.2 9.2 4.2 12 4.2 C14.8 4.2 17 6.2 17.2 10.2"
        stroke="currentColor"
        strokeWidth="1.15"
        strokeLinecap="round"
        fill="none"
        opacity="0.75"
      />
      <path
        d="M7.2 8.5 C8.5 5.8 10.2 4.8 12 4.8 C13.8 4.8 15.5 5.8 16.8 8.5"
        fill="currentColor"
        opacity="0.22"
      />

      {/* Spectacles — bridge + frames */}
      <rect x="6.8" y="9.4" width="4.6" height="3.2" rx="1.1" stroke="currentColor" strokeWidth="1.1" fill="none" />
      <rect x="12.6" y="9.4" width="4.6" height="3.2" rx="1.1" stroke="currentColor" strokeWidth="1.1" fill="none" />
      <path d="M11.4 10.8 h1.2" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
      <path d="M6.2 10.5 H5.2 M18.8 10.5 H19.8" stroke="currentColor" strokeWidth="0.9" strokeLinecap="round" opacity="0.65" />

      {/* Lens glint */}
      <circle cx="9.1" cy="10.5" r="0.55" fill="currentColor" opacity="0.45" />
      <circle cx="14.9" cy="10.5" r="0.55" fill="currentColor" opacity="0.45" />

      {/* Eyes behind lenses */}
      <circle cx="9.1" cy="10.9" r="0.75" fill="currentColor" opacity="0.7" />
      <circle cx="14.9" cy="10.9" r="0.75" fill="currentColor" opacity="0.7" />

      {/* Subtle smile — professional */}
      <path
        d="M10 12.8 Q12 13.6 14 12.8"
        stroke="currentColor"
        strokeWidth="0.9"
        strokeLinecap="round"
        fill="none"
        opacity="0.55"
      />
    </svg>
  );
}

export default ProfessionalEngineerIcon;
