import oci
import os

# Load OCI configuration from a specified file
config_file_path = os.path.expanduser("~/.oci/config_sehubjapaciaasset01")
config = oci.config.from_file(file_location=config_file_path)

# Ensure the compartment ID is set in the configuration file or environment
compartment_id = config.get("compartment_id") or os.getenv("OCI_COMPARTMENT_ID")
if not compartment_id:
    print("Error: Compartment ID must be provided in the configuration or as an environment variable.")
    exit(1)

# Compartments to Exclude
excluded_compartments = ['admincompartment']

# Initialize OCI Identity client
identity_client = oci.identity.IdentityClient(config)

def get_active_compartments(identity, root_compartment_id, excluded_compartments):
    """ Fetch all active compartments excluding specified ones """
    try:
        compartments = []
        all_compartments = oci.pagination.list_call_get_all_results(
            identity.list_compartments, root_compartment_id, lifecycle_state='ACTIVE'
        )
        for compartment in all_compartments.data:
            if compartment.name not in excluded_compartments:
                compartments.append(compartment)
        
        # Include root compartment if active
        root_compartment = identity.get_compartment(root_compartment_id).data
        if root_compartment.lifecycle_state == 'ACTIVE':
            compartments.append(root_compartment)
        
        return compartments
    except Exception as e:
        print(f"Error fetching compartments: {str(e)}")
        exit(1)

def get_subscribed_regions(identity, tenancy_id):
    """ Fetch subscribed regions for the tenancy """
    try:
        regions = [r.region_name for r in identity.list_region_subscriptions(tenancy_id).data]
        return regions
    except Exception as e:
        print(f"Error fetching subscribed regions: {str(e)}")
        exit(1)

def stop_running_instances(compartments, regions, config):
    """ Stop running instances in each compartment for each region """
    for compartment in compartments:
        print(f"Processing compartment: {compartment.name}")
        for region in regions:
            print(f"  Switching to region: {region}")
            region_config = config.copy()
            region_config.update({"region": region})
            
            compute_client = oci.core.ComputeClient(region_config)
            try:
                running_instances = compute_client.list_instances(
                    compartment.id, lifecycle_state='RUNNING'
                ).data
            except Exception as e:
                print(f"  Error listing instances in region {region} for compartment {compartment.name}: {str(e)}")
                continue

            if running_instances:
                print(f"  Found {len(running_instances)} running instances in {compartment.name}")
                for instance in running_instances:
                    # Skip instances with 'Dev' or 'Test' tags set to 'Yes'
                    if ('Dev' in instance.freeform_tags and instance.freeform_tags['Dev'] == 'Yes') or \
                       ('Test' in instance.freeform_tags and instance.freeform_tags['Test'] == 'Yes'):
                        print(f"    Skipping instance: {instance.display_name} with tags Dev or Test")
                    else:
                        try:
                            compute_client.instance_action(instance.id, "SOFTSTOP")
                            print(f"    Stopping instance: {instance.display_name}")
                        except Exception as e:
                            print(f"    Error stopping instance {instance.display_name}: {str(e)}")
            else:
                print(f"  No running instances found in {compartment.name} for region {region}")

if __name__ == "__main__":
    print("Starting script execution")

    # Fetch active compartments excluding the specified ones
    active_compartments = get_active_compartments(identity_client, compartment_id, excluded_compartments)
    
    # Fetch subscribed regions for the tenancy
    subscribed_regions = get_subscribed_regions(identity_client, config["tenancy"])

    # Stop running instances in the active compartments for each region
    stop_running_instances(active_compartments, subscribed_regions, config)

    print("Script execution completed")
