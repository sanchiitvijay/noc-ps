import logo from '../assets/logo.png';
import whiteLogo from '../assets/logo-white.png';

export default function Logo({ h = 26, white = false }) {
  if (white) {
    return <img src={whiteLogo} height={h} alt="Ferguson" />;
  }

  return (
    <>
      <img className="lgl" src={logo} height={h} alt="Ferguson" />
      <img className="lgd" src={whiteLogo} height={h} alt="Ferguson" />
    </>
  );
}
