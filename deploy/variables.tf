variable "region" {
  type    = string
  default = "us-east-1"
}

variable "name_prefix" {
  type    = string
  default = "ccm"
}

# Set false if the account already has a Config recorder (most real accounts
# do) — a second recorder is an error, and recorder pricing is per
# configuration item, so reusing the existing one is also the cheaper path.
variable "manage_recorder" {
  type    = bool
  default = true
}

# Set false if Security Hub is already enabled in this account/region.
variable "manage_security_hub" {
  type    = bool
  default = true
}
