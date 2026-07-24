import React from "react";

import { type InputRequest } from "./protocol";

interface StopConfirmationControlsProps {
  request: InputRequest;
  responsePending: boolean;
  onSubmit: (value: unknown) => void;
}

interface StopConfirmationAction {
  label: string;
  description: string;
  value: boolean;
}

export function getStopConfirmationActions(request: InputRequest): StopConfirmationAction[] {
  const squareId =
    typeof request.data.square_id === "number" && Number.isFinite(request.data.square_id)
      ? request.data.square_id
      : 0;
  const actions: StopConfirmationAction[] = [
    {
      label: "Stop Here",
      description: `End your move on Square #${squareId}`,
      value: true,
    },
  ];

  if (request.data.can_undo === true) {
    actions.push({
      label: "Undo Step",
      description: "Return to your previous square",
      value: false,
    });
  }

  return actions;
}

export function StopConfirmationControls({
  request,
  responsePending,
  onSubmit,
}: StopConfirmationControlsProps) {
  return (
    <div className="stop-action-list">
      {getStopConfirmationActions(request).map((action) => {
        const isStop = action.value;
        return (
          <button
            key={action.label}
            type="button"
            className={`stop-action-card ${isStop ? "is-stop" : "secondary is-undo"}`}
            disabled={responsePending}
            aria-label={`${action.label}. ${action.description}`}
            onClick={() => onSubmit(action.value)}
          >
            <span>
              <strong>{action.label}</strong>
              <small>{action.description}</small>
            </span>
          </button>
        );
      })}
    </div>
  );
}
