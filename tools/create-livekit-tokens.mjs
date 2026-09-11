import crypto from 'node:crypto';

const env = process.env;

const livekitUrl = env.LIVEKIT_URL || 'wss://stream-livekit.oscar-bot.com/';
const room = env.LIVEKIT_ROOM || 'oscar-lot1-room';
const apiKey = env.LIVEKIT_API_KEY;
const apiSecret = env.LIVEKIT_API_SECRET;
const ttlSeconds = Number.parseInt(env.LIVEKIT_TOKEN_TTL_SECONDS || '86400', 10);

if (
  !apiKey ||
  !apiSecret ||
  apiKey.includes('replace-with') ||
  apiSecret.includes('replace-with')
) {
  console.error('Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET.');
  console.error('Create a local server env file from .env.livekit.server.example, then run:');
  console.error('  set -a; source .env.livekit.server; set +a; npm run livekit:tokens');
  process.exit(1);
}

function base64url(input) {
  const buffer = Buffer.isBuffer(input) ? input : Buffer.from(input);
  return buffer
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function signJwt(payload) {
  const header = { alg: 'HS256', typ: 'JWT' };
  const encodedHeader = base64url(JSON.stringify(header));
  const encodedPayload = base64url(JSON.stringify(payload));
  const signature = crypto
    .createHmac('sha256', apiSecret)
    .update(`${encodedHeader}.${encodedPayload}`)
    .digest();

  return `${encodedHeader}.${encodedPayload}.${base64url(signature)}`;
}

function createToken({
  identity,
  name,
  metadata,
  canPublish,
  canSubscribe,
  canPublishData,
  canPublishSources,
}) {
  const now = Math.floor(Date.now() / 1000);
  const video = {
    room,
    roomJoin: true,
    canPublish,
    canSubscribe,
    canPublishData,
  };

  if (canPublishSources?.length) {
    video.canPublishSources = canPublishSources;
  }

  return signJwt({
    iss: apiKey,
    sub: identity,
    name,
    nbf: now,
    exp: now + ttlSeconds,
    video,
    metadata: JSON.stringify(metadata),
  });
}

const publisherIdentity = env.LIVEKIT_PUBLISHER_IDENTITY || 'simulateur-robot-isaac-1';
const commandIdentity = env.LIVEKIT_COMMAND_IDENTITY || 'isaac-command-agent';
const viewerIdentity = env.LIVEKIT_VIEWER_IDENTITY || 'oscar-front-viewer';

const publisherToken = createToken({
  identity: publisherIdentity,
  name: 'Isaac Sim Robot',
  metadata: {
    source: 'isaac-sim',
    robot: 'unitree-g1',
    projection: 'flat',
    layout: 'stereo-left-right',
  },
  canPublish: true,
  canSubscribe: false,
  canPublishData: true,
  canPublishSources: ['camera'],
});

const viewerToken = createToken({
  identity: viewerIdentity,
  name: 'OSCAR Front Viewer',
  metadata: {
    role: 'operator-viewer',
    app: 'oscar',
  },
  canPublish: false,
  canSubscribe: true,
  canPublishData: true,
});

const commandToken = createToken({
  identity: commandIdentity,
  name: 'Isaac Command Agent',
  metadata: {
    role: 'isaac-command-agent',
    robot: 'unitree-g1',
    inputTopic: 'oscar.xr.input',
    commandTopic: 'oscar.robot.command',
  },
  canPublish: false,
  canSubscribe: true,
  canPublishData: true,
});

console.log(JSON.stringify({
  livekitUrl,
  room,
  publisher: {
    identity: publisherIdentity,
    token: publisherToken,
  },
  commandAgent: {
    identity: commandIdentity,
    token: commandToken,
  },
  viewer: {
    identity: viewerIdentity,
    token: viewerToken,
  },
  frontendEnv: {
    VITE_LIVEKIT_URL: livekitUrl,
    VITE_LIVEKIT_ROOM: room,
    VITE_LIVEKIT_TOKEN: viewerToken,
  },
}, null, 2));
