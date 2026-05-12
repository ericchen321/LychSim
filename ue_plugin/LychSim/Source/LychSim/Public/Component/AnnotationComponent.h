// Weichao Qiu @ 2017
#pragma once

#include "Runtime/Engine/Classes/Components/StaticMeshComponent.h"
#include "Runtime/Engine/Public/SkeletalRenderPublic.h"

#include "AnnotationComponent.generated.h"


// TODO: Might need to annotate every frame if there are new actors got spawned
/** A proxy component class to render annotation color
 * Should be attached to a MeshComponent to provide annotation color for AnnotationCamSensor
*/
UCLASS(meta = (BlueprintSpawnableComponent))
// class UAnnotationComponent : public UMeshComponent
// Note: if define UAnnotationComponent as a UMeshComponent, then some confusion will raise
// for example: compare the number of MeshComponent and AnnotationComponent
class LYCHSIM_API UAnnotationComponent : public UPrimitiveComponent
{
	GENERATED_BODY()

public:
	UAnnotationComponent(const FObjectInitializer& ObjectInitializer);

	virtual FPrimitiveSceneProxy* CreateSceneProxy() override;

	virtual FBoxSphereBounds CalcBounds(const FTransform & LocalToWorld) const override;

	virtual void TickComponent(float DeltaTime,
		enum ELevelTick TickType,
		FActorComponentTickFunction * ThisTickFunction) override;

	void SetAnnotationColor(FColor AnnotationColor);

	FColor GetAnnotationColor();

	virtual void OnRegister() override;

	/** Restrict the annotation to a single section/element, empty means all sections. */
	void SetAllowedElement(int32 ElementIndex);

	/** Restrict the annotation to a list of sections/elements. */
	void SetAllowedElements(const TArray<int32>& InElements);

	/** Remove any per-element restriction and annotate the full mesh. */
	void ClearAllowedElements();

	/** Check whether this annotation should render the provided element index. */
	bool AllowsElement(int32 ElementIndex) const;

	/** Accessor used by the scene proxy. */
	const TArray<int32>& GetAllowedElements() const { return AllowedElements; }

	/** Force the component to update to capture changes from the parent */
	void ForceUpdate();

private:
	// FParentMeshInfo ParentMeshInfo;
	// TSharedPtr<class FParentMeshInfo> ParentMeshInfo;

	UPROPERTY()
	UMaterial* AnnotationMaterial;

	UPROPERTY()
	UMaterialInstanceDynamic* AnnotationMID;

	FColor AnnotationColor;

	bool bSkeletalMesh; // indicate whether this is for a SkeletalMesh

	/** Optional list of mesh element indices rendered by this annotation. Empty means all elements. */
	TArray<int32> AllowedElements;

	FPrimitiveSceneProxy* CreateSceneProxy(UStaticMeshComponent* StaticMeshComponent);
	FPrimitiveSceneProxy* CreateSceneProxy(USkeletalMeshComponent* SkeletalMeshComponent);
};
