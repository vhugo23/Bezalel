import { Link } from 'react-router';
import { Button } from '../components/ui';

export function PrivacyPage() {
 return <div className="app-shell"><main className="page"><div className="wrap"><section className="card lesson-body">
  <h1>Your practice data</h1>
  <p>PrepCrew saves your practice so you can return to your plan and continue learning.</p>
  <h2>What is saved</h2>
  <p>Your account name and email, preparation goals, imported source text, conversations, whiteboard snapshots, simulator actions, feedback, lessons and practice progress are stored on the server. Passwords are stored as hashes. Signing out ends your account session; it does not delete your saved practice.</p>
  <h2>AI and voice processing</h2>
  <p>In live mode, relevant preparation text, conversation and whiteboard images are sent to Gemini for coaching and review. Cloud voice uses ElevenLabs for speech recognition and playback. When local speech is available, speech models run on your device and recognized text is sent to the server for coaching. Verified learning gaps may be synchronized with Backboard to personalize later practice.</p>
  <h2>Your device</h2>
  <p>Microphone access starts when you start voice. Stop voice to release the microphone. You can type instead. Local speech downloads and caches models in your browser; clearing this site's browser data removes those local caches, but does not erase server records. A paired drawing device has limited access until the interview ends or its access expires.</p>
  <h2>Current account controls</h2>
  <p>You can sign out, return to saved practice from your history, and download your locally stored practice records as JSON from Account. The export excludes binary attachments, authentication credentials and provider-only data. Self-service password recovery and account deletion are not available yet. For this demo, use fictional preparation material and avoid uploading confidential documents or information about other people.</p>
  <h2>Practice feedback</h2>
  <p>AI-generated feedback and lessons can be wrong. Scores use authored practice criteria and have not been calibrated as hiring assessments. Recorded demonstrations and simulated hardware are labeled in the app.</p>
  <Button asChild variant="outline"><Link to="/plan">Return to PrepCrew</Link></Button>
 </section></div></main></div>;
}
