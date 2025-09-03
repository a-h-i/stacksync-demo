import * as pulumi from "@pulumi/pulumi";
import * as gcp from "@pulumi/gcp";

const imageConfig = new pulumi.Config("image");
const imageName = imageConfig.require("name");

const gcpConfig = new pulumi.Config("gcp");
const project = gcpConfig.require("project");
const region = gcpConfig.require("region");


const repo = new gcp.artifactregistry.Repository('ghcr-remote', {
    location: region,
    format: "DOCKER",
    repositoryId: "ghcr",
    mode: 'REMOTE_REPOSITORY',
    description: "Remote proxy to GitHub Container Registry (ghcr.io)",
    remoteRepositoryConfig: {
        dockerRepository: {
            customRepository: {
                uri: "https://ghcr.io",
            }
        }
    }
})

const svc = new gcp.cloudrunv2.Service('stacksync-demo', {
    name: 'stacksync-demo',
    location: region,
    ingress: "INGRESS_TRAFFIC_ALL",
    template: {
        scaling: {
            minInstanceCount: 1,
            maxInstanceCount: 1,
        },
        containers: [
            {
                image: `${region}-docker.pkg.dev/${project}/ghcr/a-h-i/stacksync-demo:${imageName}`,
                ports: {
                    containerPort: 8080,
                },
                envs: [
                    {
                        name: "NSJAIL_MODE",
                        value: "strict"
                    }
                ],
                resources: {
                    limits: {
                        cpu: "1",
                        memory: "1Gi"
                    }
                }
            }
        ]
    }
}, {
    dependsOn: [repo]
})


const invoker = new gcp.cloudrunv2.ServiceIamMember("public-invoker", {
    name: svc.name,       // resource name of the service
    location: region,
    role: "roles/run.invoker",
    member: "allUsers",
    project: project,
  });

export const url = svc.uri;
export const serviceNameOut = svc.name;