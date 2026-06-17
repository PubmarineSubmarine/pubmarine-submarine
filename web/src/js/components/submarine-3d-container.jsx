import Submarine3D from "../submarine-3d.jsx";
import { orientation } from "../gamepad-service.js";

export function Submarine3DContainer() {
  const ori = orientation.value;

  return (
    <div class="overlay-submarine-3d">
      <Submarine3D
        modelPath="/static/subsanwich.obj"
        orientation={ori}
      />
    </div>
  );
}
