terraform {
  required_version = ">= 1.13.0, < 2.0.0"
  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "0.11.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "2.17.0"
    }
  }
}

variable "cluster_name" {
  type    = string
  default = "platform-delivery-lab"
}

variable "http_port" {
  type    = number
  default = 8088
}

resource "kind_cluster" "lab" {
  name            = var.cluster_name
  node_image      = "kindest/node:v1.35.0"
  wait_for_ready  = true
  kubeconfig_path = abspath("${path.module}/../.kube/config")
  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"
    node {
      role = "control-plane"
      extra_port_mappings {
        container_port = 30080
        host_port      = var.http_port
        listen_address = "127.0.0.1"
      }
      extra_port_mappings {
        container_port = 30300
        host_port      = 3008
        listen_address = "127.0.0.1"
      }
      extra_port_mappings {
        container_port = 30909
        host_port      = 9098
        listen_address = "127.0.0.1"
      }
    }
  }
}

provider "helm" {
  kubernetes {
    host                   = kind_cluster.lab.endpoint
    client_certificate     = kind_cluster.lab.client_certificate
    client_key             = kind_cluster.lab.client_key
    cluster_ca_certificate = kind_cluster.lab.cluster_ca_certificate
  }
}

resource "helm_release" "ingress" {
  name             = "ingress"
  namespace        = "ingress-nginx"
  create_namespace = true
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.15.1"
  timeout          = 600
  values           = [file("${path.module}/values/ingress.yaml")]
}

resource "helm_release" "rollouts" {
  name             = "argo-rollouts"
  namespace        = "argo-rollouts"
  create_namespace = true
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-rollouts"
  version          = "2.43.6"
  timeout          = 600
  values           = [file("${path.module}/values/rollouts.yaml")]
}

resource "helm_release" "prometheus" {
  name             = "prometheus"
  namespace        = "monitoring"
  create_namespace = true
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "prometheus"
  version          = "29.36.1"
  timeout          = 600
  values           = [file("${path.module}/values/prometheus.yaml")]
}

resource "helm_release" "grafana" {
  name             = "grafana"
  namespace        = "monitoring"
  create_namespace = true
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "grafana"
  version          = "10.5.15"
  timeout          = 600
  values = [file("${path.module}/values/grafana.yaml"), yamlencode({
    dashboards = { default = { delivery = { json = file("${path.module}/../ops/dashboard.json") } } }
  })]
}

output "console" {
  value = "http://localhost:${var.http_port}"
}

output "grafana" {
  value = "http://localhost:3008/d/lab/platform-delivery-lab"
}
