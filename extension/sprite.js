window.SnowBallSprite = (state = 'waking') => {
  const asleep = state === 'sleeping';

  const eyes = asleep
    ? '<g class="eyes"><path d="M24 15h3v1h-3zm7 0h3v1h-3z" fill="#38204f"/></g>'
    : '<g class="eyes eyes-open"><path d="M25 13h2v3h-2zm7 0h2v3h-2z" fill="#38204f"/><path d="M25 13h1v1h-1zm7 0h1v1h-1z" fill="white"/></g>';

  return `
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 40 32"
      shape-rendering="crispEdges"
      aria-hidden="true"
    >
      <g class="body">
        <path d="M12 17h15v2h5v7h-3v2H10v-2H8v-6h4z" fill="#593684"/>
        <path d="M13 18h13v2h4v5H11v-4h2z" fill="#a774dc"/>
        <path d="M13 23h15v3H13z" fill="#d8baf8"/>
      </g>
      <g class="tail">
        <path d="M15 22h-3v3H8v-2H5v-2H3v-3H1v-4H0v-4h2V7h2V4h4v2h4v3h-2v3H8v4h2v3h3v1h3z" fill="#593684"/>
        <path d="M11 21H8v2H6v-2H4v-3H2v-4H1v-4h2V8h2V6h3v2h2v2H8v3H6v3h2v2h3v1h3v2h-3z" fill="#bb8def"/>
        <path d="M3 10h2V8h2v2H5v2H3zm-1 4h2v3H2zm3 5h2v2H5z" fill="#d8baf8"/>
      </g>
      <g class="head">
        <path d="M21 6h4v3h8V6h4v13h-2v3H23v-3h-2z" fill="#593684"/>
        <path d="M22 8h2v3h10V8h2v10h-2v3H24v-3h-2z" fill="#bb8def"/>
        <path d="M23 9h1v3h-1zm11 0h1v3h-1z" fill="#f1b3e1"/>
        ${eyes}
        <!-- Small nose only; no mouth in speaking or pointing states. -->
        <path d="M28 17h3v1h-3z" fill="#8b4db8"/>
        <path d="M23 17h2v1h-2zm10 0h2v1h-2z" fill="#f1b3e1"/>
      </g>
      <g class="paws">
        <path d="M13 26h5v4h-5zm11 0h5v4h-5z" fill="#593684"/>
        <path d="M14 26h3v3h-3zm11 0h3v3h-3z" fill="#d8baf8"/>
      </g>
      ${asleep ? '<text x="8" y="7" font-size="6" fill="#8662b0">z z</text>' : ''}
      ${state === 'confused' ? '<text x="7" y="10" font-size="9" fill="#593684">?</text>' : ''}
      ${state === 'celebrating' ? '<path d="M13 6h2V4h2v2h2v2h-2v2h-2V8h-2z" fill="#ef82c1"/>' : ''}
      ${state === 'sad' ? '<path d="M33 17h1v3h-1z" fill="#72bcec"/>' : ''}
    </svg>
  `;
};
