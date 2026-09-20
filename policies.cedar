// CivicFlow dispatch authorization policies.
// @id / @reason annotations are read by cedar_eval.py to explain every decision.

@id("EmergencyDispatchPolicy")
@reason("Municipal Officers may approve emergency dispatch.")
permit (
    principal in Role::"MunicipalOfficer",
    action == Action::"ApproveDispatch",
    resource
);

@id("SupervisorFullAuthority")
@reason("Supervisors hold full dispatch authority.")
permit (
    principal in Role::"Supervisor",
    action == Action::"ApproveDispatch",
    resource
);

@id("NoSelfDispatchOnHighUrgency")
@reason("FieldTechnician cannot authorize urgency >= 4 dispatches.")
forbid (
    principal in Role::"FieldTechnician",
    action == Action::"ApproveDispatch",
    resource
)
when { resource.urgency >= 4 };

@id("FieldTechLowUrgencyElectrical")
@reason("Field Technicians may self-dispatch low-urgency Electrical & Power work up to Rs 25,000.")
permit (
    principal in Role::"FieldTechnician",
    action == Action::"ApproveDispatch",
    resource
)
when {
    resource.urgency < 4 &&
    resource.category == "Electrical & Power" &&
    resource.cost <= 25000
};
