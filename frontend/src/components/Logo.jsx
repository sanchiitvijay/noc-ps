import logo from "../assets/logo.png";
import whiteLogo from "../assets/logo-white.png";

/**
 * Brand wordmark. Renders the colour logo on light surfaces and the white
 * logo on the navy rail / dark hero panels.
 */
export default function Logo({ className = "h-7 w-auto", white = false, alt = "Ferguson" }) {
  return <img src={white ? whiteLogo : logo} alt={alt} className={className} />;
}
