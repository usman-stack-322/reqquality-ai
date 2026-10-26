import React from 'react';

// Brand text sits beside the image in each lockup, so the mark is decorative.
export default function BrandLogo({ size = 40 }) {
  return <img className="brand-logo" src="/favicon-192.png" srcSet="/favicon-192.png 192w, /reqquality-logo.png 512w" sizes={`${size}px`} alt="" width={size} height={size} />;
}
