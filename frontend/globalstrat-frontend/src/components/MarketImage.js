/**
 * Shared market identity graphics.
 * Maps market codes to their images in /public/images/.
 *
 * Usage:
 *   <MarketImage code="NA" />              — 48px rounded thumbnail (default)
 *   <MarketImage code="EA" size={80} />    — 80px thumbnail
 *   <MarketImage code="EU" variant="banner" /> — full-width banner header
 */

import React from 'react';

const MARKET_IMAGES = {
  NA:  { src: '/images/north-america.png',  alt: 'North America' },
  EA:  { src: '/images/east-asia.png',      alt: 'East Asia' },
  EU:  { src: '/images/western-europe.png', alt: 'Western Europe' },
  SA:  { src: '/images/south-america.png',  alt: 'South America' },
  WA:  { src: '/images/west-africa.png',    alt: 'West Africa' },
  // Aliases for longer codes
  'North America':  { src: '/images/north-america.png',  alt: 'North America' },
  'East Asia':      { src: '/images/east-asia.png',      alt: 'East Asia' },
  'Western Europe': { src: '/images/western-europe.png', alt: 'Western Europe' },
  'South America':  { src: '/images/south-america.png',  alt: 'South America' },
  'West Africa':    { src: '/images/west-africa.png',    alt: 'West Africa' },
};

const MarketImage = ({ code, name, size = 48, variant = 'thumbnail', style: extraStyle }) => {
  const entry = MARKET_IMAGES[code] || MARKET_IMAGES[name];
  if (!entry) return null;

  if (variant === 'banner') {
    return (
      <img
        src={entry.src}
        alt={entry.alt}
        loading="lazy"
        style={{
          width: '100%', height: 200, objectFit: 'cover',
          display: 'block', borderRadius: 2,
          ...extraStyle,
        }}
      />
    );
  }

  // Thumbnail (default)
  return (
    <img
      src={entry.src}
      alt={entry.alt}
      loading="lazy"
      style={{
        width: size, height: size,
        borderRadius: size >= 60 ? 8 : 6,
        objectFit: 'cover',
        flexShrink: 0,
        ...extraStyle,
      }}
    />
  );
};

export default MarketImage;
export { MARKET_IMAGES };
